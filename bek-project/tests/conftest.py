"""
Общие настройки тестов.

Переменные окружения выставляются ДО импорта app: тесты не зависят от вашего .env и не упираются в лимиты попыток.
Тесты с БД идут в отдельной схеме внутри DATABASE_URL (создаётся и удаляется самими тестами),
ваши таблицы они не трогают. Тесты на реальных моделях запускаются только с флагом --run-models.
"""

import os
import secrets
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["MIN_SECONDS_BETWEEN_ATTEMPTS"] = "0"
os.environ["ATTEMPTS_PER_HOUR"] = "100000"
os.environ["ATTEMPTS_PER_DAY"] = "100000"
os.environ["STUB_MODELS"] = "1"   # по умолчанию тесты не поднимают ни BERT, ни языковые модели
os.environ["STUB_LLM"] = "1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from helpers import RecordingBackend  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--run-models", action="store_true", help="запустить тесты на реальных моделях (BERT и GGUF, около минуты на загрузку)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-models"):
        return
    skip = pytest.mark.skip(reason="нужен флаг --run-models (реальные модели)")
    for item in items:
        if "models" in item.keywords:
            item.add_marker(skip)


# ── PostgreSQL в отдельной схеме ─────────────────────────────────────────────
def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="session")
async def db_schema():
    """
    Схема test_<случайно> с таблицами приложения. Приложение на время тестов получает свой движок, у которого
    search_path указан в параметрах подключения (SET в обработчике connect откатывается при возврате соединения в пул
    и тесты уходили бы в рабочие таблицы). В конце проверяется, что в рабочей схеме тестовых данных не появилось.
    """
    import asyncpg
    from sqlalchemy.ext.asyncio import create_async_engine

    from app import settings
    from app.db import SessionLocal
    from app.models import Base

    test_login = r"^(t_[0-9a-f]{10}|auth_case_[12])$"

    schema = f"test_{secrets.token_hex(4)}"
    try:
        conn = await asyncpg.connect(_asyncpg_dsn(settings.DATABASE_URL), timeout=5)
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        await conn.close()
    except Exception as e:  # нет БД, неверный пароль, нет прав на создание схемы
        pytest.skip(f"PostgreSQL недоступен или нет прав на CREATE SCHEMA: {type(e).__name__}: {e}")

    test_engine = create_async_engine(
        # public в пути быть не должно: иначе SQLAlchemy увидит там рабочие таблицы и решит, что своих создавать не нужно
        settings.DATABASE_URL, pool_pre_ping=True, connect_args={"server_settings": {"search_path": schema}}
    )
    original_bind = SessionLocal.kw.get("bind")
    SessionLocal.configure(bind=test_engine)       # все SessionLocal в приложении (auth, game, api) теперь ходят в тестовую схему

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:               # страховка: убеждаемся, что сессии приложения действительно в тестовой схеме
        from sqlalchemy import text

        assert (await db.execute(text("select current_schema()"))).scalar() == schema
        users_in = (await db.execute(text(
            "select n.nspname from pg_class c join pg_namespace n on n.oid = c.relnamespace where c.oid = to_regclass('users')"
        ))).scalar()
        assert users_in == schema, f"сессии приложения должны видеть таблицу users в тестовой схеме, а видят в {users_in}"
    yield schema

    await test_engine.dispose()
    SessionLocal.configure(bind=original_bind)
    conn = await asyncpg.connect(_asyncpg_dsn(settings.DATABASE_URL))
    leaked = None
    if await conn.fetchval("select to_regclass('public.users')"):
        leaked = await conn.fetchval("select count(*) from public.users where login ~ $1", test_login)
    await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await conn.close()
    assert not leaked, f"тесты записали {leaked} игроков в рабочую схему public: изоляция сломана"


@pytest.fixture(scope="session")
async def api(db_schema):
    """HTTP-клиент к настоящему приложению (lifespan, маршруты, БД) с заглушками вместо моделей."""
    from app import settings
    from app.api import app

    patch = pytest.MonkeyPatch()
    patch.setattr(settings, "STUB_MODELS", True)
    patch.setattr("app.pipeline.create_backend", lambda: RecordingBackend())
    async with app.router.lifespan_context(app):
        patch.undo()          # пайплайн уже создан; остальным тестам настройки возвращаются
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            client.app = app
            yield client


@pytest.fixture
def backend(api):
    """Языковые модели приложения (запись вызовов, задержки, сбои); состояние сбрасывается после теста."""
    pipeline = api.app.state.pipeline
    backend = pipeline.backend
    backend.reset()
    pipeline._replies._items.clear()      # слова в пуле повторяются: чужой кэш не должен подменять ответ модели
    pipeline._topics._items.clear()
    yield backend
    backend.reset()


class Player:
    def __init__(self, client: httpx.AsyncClient, login: str, headers: dict):
        self.client, self.login, self.headers = client, login, headers

    async def predict(self, text: str, pass_id: str = "tony_stark") -> httpx.Response:
        return await self.client.post("/predict", headers=self.headers, json={"pass_id": pass_id, "text": text})

    async def get(self, path: str) -> httpx.Response:
        return await self.client.get(path, headers=self.headers)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self.client.post(path, headers=self.headers, **kwargs)

    async def secret(self, pass_id: str = "tony_stark") -> str:
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import User, UserPass

        async with SessionLocal() as db:
            return await db.scalar(
                select(UserPass.secret).join(User, User.id == UserPass.user_id).where(User.login == self.login, UserPass.pass_id == pass_id)
            )

    async def used_secrets(self, pass_id: str = "tony_stark") -> list:
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import User, UserPass

        async with SessionLocal() as db:
            return await db.scalar(
                select(UserPass.used_secrets).join(User, User.id == UserPass.user_id).where(User.login == self.login, UserPass.pass_id == pass_id)
            )

    async def attempts(self) -> list:
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import Attempt, User

        async with SessionLocal() as db:
            rows = await db.scalars(
                select(Attempt).join(User, User.id == Attempt.user_id).where(User.login == self.login).order_by(Attempt.id)
            )
            return list(rows)


@pytest.fixture
def make_player(api):
    """Фабрика игроков: регистрирует нового и по умолчанию доводит прохождение до свободного промпта."""

    async def make(free_prompt: bool = True, pass_id: str = "tony_stark") -> Player:
        login = f"t_{secrets.token_hex(5)}"
        response = await api.post("/auth/register", json={"login": login, "password": "correct-horse-1"})
        assert response.status_code == 201, response.text
        player = Player(api, login, {"Authorization": f"Bearer {response.json()['token']}"})
        if free_prompt:
            assert (await player.post(f"/passes/{pass_id}/start")).status_code == 200
            assert (await player.post(f"/passes/{pass_id}/phase", json={"phase": "puzzle"})).status_code == 200
            assert (await player.post(f"/passes/{pass_id}/phase", json={"phase": "free_prompt"})).status_code == 200
        return player

    return make
