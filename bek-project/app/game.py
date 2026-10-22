"""
Прогресс игрока: прохождения, фазы, найденные подсказки, уровень мира.

Фазы: investigation → puzzle → free_prompt → done. О первых двух переходах сообщает клиент,
done ставит только сервер, когда игрок ввёл слово-якорь (см. /predict в api.py).
Слово-якорь в ответы не попадает никогда.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app import settings
from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import PHASES, UserGameState, UserPass
from app.passwords import pick_secret
from app.schemas import (
    ClueRequest,
    PassState,
    PhaseRequest,
    ProgressResponse,
    WorldLevelInfo,
    WorldLevelRequest,
    WorldLevelsResponse,
)

router = APIRouter(tags=["game"])

# Подсказки собирают в расследовании и после выхода из паззла (новые тоже сохраняются)
CLUE_PHASES = ("investigation", "puzzle")
MAX_CLUES_PER_PASS = 100


def _check_pass_id(pass_id: str) -> None:
    if pass_id not in settings.PASS_IDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Неизвестное прохождение '{pass_id}'")


def pass_state(pass_id: str, passes: dict[str, UserPass]) -> PassState:
    row = passes.get(pass_id)
    return PassState(
        pass_id=pass_id,
        started=row is not None,
        phase=row.phase if row else "",
        completed=row is not None and row.completed_at is not None,
        collected_clues=list(row.collected_clues) if row else [],
    )


async def _load_passes(db: AsyncSession, user: CurrentUser) -> dict[str, UserPass]:
    rows = await db.scalars(select(UserPass).where(UserPass.user_id == user.id))
    return {row.pass_id: row for row in rows}


async def _get_state(db: AsyncSession, user: CurrentUser) -> UserGameState:
    state = await db.get(UserGameState, user.id)
    if state is None:  # на случай аккаунта, созданного в обход /auth/register
        state = UserGameState(user_id=user.id, world_level=settings.DEFAULT_WORLD_LEVEL)
        db.add(state)
        await db.flush()
    return state


async def _get_started_pass(db: AsyncSession, user: CurrentUser, pass_id: str) -> UserPass:
    _check_pass_id(pass_id)
    row = await db.get(UserPass, (user.id, pass_id), with_for_update=True)
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Прохождение не начато: сначала /passes/{pass_id}/start")
    return row


@router.get("/me/progress", response_model=ProgressResponse)
async def get_progress(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Всё, что нужно клиенту при запуске: уровень мира, текущее прохождение, фазы и подсказки."""
    state = await _get_state(db, user)
    passes = await _load_passes(db, user)
    await db.commit()
    return ProgressResponse(
        login=user.login,
        display_name=user.display_name,
        world_level=state.world_level,
        current_pass_id=state.current_pass_id or "",
        passes=[pass_state(pass_id, passes) for pass_id in settings.PASS_IDS],
    )


@router.post("/passes/{pass_id}/start", response_model=PassState)
async def start_pass(
    pass_id: str, user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Вход на уровень (все уровни открыты, проходить можно в любом порядке и параллельно).
    Не начато — создаётся с новым словом. Начато — продолжается с сохранённой фазы
    (незаконченный этап клиент начинает заново). Пройдено (done) — перепрохождение: фаза и подсказки
    сбрасываются, выдаётся новое слово, completed_at сохраняется.
    """
    _check_pass_id(pass_id)
    category = settings.LEVEL_TO_CATEGORY[pass_id]

    row = await db.get(UserPass, (user.id, pass_id), with_for_update=True)
    if row is None:
        secret, used = pick_secret(category, [])
        row = UserPass(
            user_id=user.id, pass_id=pass_id, phase="investigation",
            collected_clues=[], secret=secret, used_secrets=used,
        )
        db.add(row)
    elif row.phase == "done":
        secret, used = pick_secret(category, list(row.used_secrets))
        row.phase = "investigation"
        row.collected_clues = []
        row.secret = secret
        row.used_secrets = used
        row.started_at = func.now()

    state = await _get_state(db, user)
    state.current_pass_id = pass_id
    try:
        await db.commit()
    except IntegrityError:  # параллельный /start того же прохождения уже создал строку
        await db.rollback()

    passes = await _load_passes(db, user)
    result = pass_state(pass_id, passes)
    await db.commit()
    return result


@router.post("/passes/{pass_id}/clues", response_model=PassState)
async def add_clue(
    pass_id: str, data: ClueRequest,
    user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Найденная подсказка (отправляется сразу при нахождении). Повтор и поздние находки игнорируются."""
    row = await _get_started_pass(db, user, pass_id)
    clue = data.clue.strip()
    if row.phase in CLUE_PHASES and clue and clue not in row.collected_clues:
        if len(row.collected_clues) >= MAX_CLUES_PER_PASS:
            raise HTTPException(status.HTTP_409_CONFLICT, "Слишком много подсказок для одного прохождения")
        row.collected_clues = [*row.collected_clues, clue]

    result = pass_state(pass_id, await _load_passes(db, user))
    await db.commit()
    return result


@router.post("/passes/{pass_id}/phase", response_model=PassState)
async def set_phase(
    pass_id: str, data: PhaseRequest,
    user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """
    Переход вперёд: puzzle — подсказки собраны, free_prompt — паззл решён.
    Повтор текущей фазы — без изменений; назад и в done — 409.
    """
    row = await _get_started_pass(db, user, pass_id)
    current, target = PHASES.index(row.phase), PHASES.index(data.phase)
    if target < current or row.phase == "done":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Нельзя перейти из {row.phase} в {data.phase}")
    row.phase = data.phase

    result = pass_state(pass_id, await _load_passes(db, user))
    await db.commit()
    return result


@router.get("/world-levels", response_model=WorldLevelsResponse)
async def get_world_levels(
    request: Request, user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Уровни мира (классификатор сложности) и выбранный игроком."""
    state = await _get_state(db, user)
    await db.commit()
    available = _available_world_levels(request)
    return WorldLevelsResponse(
        current=state.world_level,
        levels=[
            WorldLevelInfo(level=level, name=name, available=level in available)
            for level, name in settings.WORLD_LEVELS.items()
        ],
    )


@router.put("/me/world-level", response_model=WorldLevelsResponse)
async def set_world_level(
    data: WorldLevelRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    if data.world_level not in _available_world_levels(request):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Уровень мира {data.world_level} сейчас недоступен")
    state = await _get_state(db, user)
    state.world_level = data.world_level
    await db.commit()
    return await get_world_levels(request, user, db)


def _available_world_levels(request: Request) -> list[int]:
    pipeline = getattr(request.app.state, "pipeline", None)
    return pipeline.available_world_levels if pipeline else []
