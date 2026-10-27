"""
Таблицы данных игрока. Схему меняем только миграциями Alembic (alembic/versions).

Справочные данные (уровни, призраки, пулы слов) в БД не хранятся — они в коде.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PHASES = ("investigation", "puzzle", "free_prompt", "done")
ROLES = ("player", "admin")
LOGIN_PATTERN = r"^[a-z0-9_.-]{3,32}$"


class Base(DeclarativeBase):
    # Предсказуемые имена ограничений — чтобы миграции могли их найти и удалить
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"login ~ '{LOGIN_PATTERN}'", name="login_format"),
        CheckConstraint(f"role IN {ROLES}", name="role_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    # Хранится в нижнем регистре — уникальность без учёта регистра
    login: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), server_default="player")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    """Сессия на устройство. В БД только SHA-256 токена, сам токен знает лишь клиент."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class UserGameState(Base):
    __tablename__ = "user_game_state"
    __table_args__ = (CheckConstraint("world_level BETWEEN 1 AND 4", name="world_level_range"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # Уровень мира = ступень защитника (settings.FINAL_LADDER), выбирает игрок (settings.WORLD_LEVELS)
    world_level: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    current_pass_id: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserPass(Base):
    """
    Прогресс по прохождению. Одна строка на (игрок, прохождение), в том числе при перепрохождении:
    phase сбрасывается, completed_at остаётся — прохождение закрыто, если completed_at не NULL.
    """

    __tablename__ = "user_passes"
    __table_args__ = (CheckConstraint(f"phase IN {PHASES}", name="phase_valid"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pass_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    phase: Mapped[str] = mapped_column(String(16), server_default="investigation")
    # Найденные подсказки: полный текст карточки паззла (puzzleText в Unity)
    collected_clues: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    # Журнал прочитанных разговоров: [{"entries": [{"name": ..., "text": ...}, ...]}, ...], без повторов
    journal: Mapped[list[dict]] = mapped_column(JSONB, server_default="[]")
    # Слово-якорь: только на сервере, клиенту не отдаётся
    secret: Mapped[str] = mapped_column(Text)
    used_secrets: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Attempt(Base):
    """Журнал попыток: одна строка = одна отправка в свободном промпте."""

    __tablename__ = "attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "pass_id"], ["user_passes.user_id", "user_passes.pass_id"], ondelete="CASCADE"
        ),
        # Подсчёт попыток за период для лимита
        Index("ix_attempts_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # NULL — песочница вне сюжета
    pass_id: Mapped[Optional[str]] = mapped_column(String(32))
    prompt_text: Mapped[str] = mapped_column(Text)
    # Ответ языковой модели (мини-LLM или защитника, в том числе из кэша повторов).
    # NULL — модель не ответила (слово введено сразу, запрос отсёк шлюз или гигиена)
    llm_response: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean)
    # Трасса пайплайна: tier, stages (этап, модель, решение, время, токены), blocked_by (hygiene | gate),
    # leaked (слово есть в ответе защитника), cache_hit, error
    classifier_output: Mapped[dict] = mapped_column(JSONB)
    world_level: Mapped[int] = mapped_column(SmallInteger)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
