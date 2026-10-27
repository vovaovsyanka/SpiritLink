"""
Модели запросов и ответов API.

Ответы плоские и без null: Unity разбирает их через JsonUtility, который не понимает null
у примитивов, словари и даты. Время — строкой ISO-8601 в UTC.
"""

import re
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app import settings
from app.models import LOGIN_PATTERN
from app.text_utils import clean_input

PassId = Literal["tony_stark", "subnautica", "cyberpunk"]


# ── Аутентификация ───────────────────────────────────────────────────────────

class Credentials(BaseModel):
    login: str = Field(..., description="3–32 символа: латиница, цифры, _ . -; регистр не важен")
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(LOGIN_PATTERN, value):
            raise ValueError("Логин: 3–32 символа, латинские буквы, цифры, _ . -")
        return value


class RegisterRequest(Credentials):
    display_name: str = Field("", max_length=64, description="Имя в игре; по умолчанию — логин")


class LoginRequest(Credentials):
    pass


class TokenResponse(BaseModel):
    token: str = Field(..., description="Передавать в заголовке Authorization: Bearer <token>")
    expires_at: str


# ── Прогресс ─────────────────────────────────────────────────────────────────

class JournalEntry(BaseModel):
    name: str = Field("", max_length=200, description="Кто говорит")
    text: str = Field(..., max_length=2000, description="Реплика")


class JournalDialogue(BaseModel):
    entries: list[JournalEntry]


class JournalRequest(BaseModel):
    entries: list[JournalEntry] = Field(..., min_length=1, max_length=200, description="Реплики одного разговора")


class PassState(BaseModel):
    pass_id: str
    started: bool
    phase: str = Field(..., description="investigation | puzzle | free_prompt | done; пусто, если не начато")
    completed: bool = Field(..., description="Прохождение закрыто хотя бы раз (сохраняется при перепрохождении)")
    collected_clues: list[str]
    journal: list[JournalDialogue] = Field(..., description="Прочитанные разговоры по порядку, без повторов")


class ProgressResponse(BaseModel):
    login: str
    display_name: str
    world_level: int
    current_pass_id: str = Field(..., description="Пусто, если ни одно прохождение не начато")
    passes: list[PassState]


class ClueRequest(BaseModel):
    clue: str = Field(..., min_length=1, max_length=500, description="Полный текст карточки (puzzleText)")


class PhaseRequest(BaseModel):
    phase: Literal["puzzle", "free_prompt"] = Field(
        ..., description="puzzle — подсказки собраны; free_prompt — паззл решён. done ставит только сервер"
    )


class WorldLevelInfo(BaseModel):
    level: int
    name: str
    available: bool = Field(..., description="Модель уровня загружена на сервере")


class WorldLevelsResponse(BaseModel):
    current: int
    levels: list[WorldLevelInfo]


class WorldLevelRequest(BaseModel):
    world_level: int = Field(..., ge=min(settings.WORLD_LEVELS), le=max(settings.WORLD_LEVELS))


# ── Свободный промпт ─────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    pass_id: PassId = Field(
        ...,
        validation_alias=AliasChoices("pass_id", "level"),
        description="Прохождение: tony_stark (кат. 3), subnautica (кат. 4), cyberpunk (кат. 5)",
    )
    text: str = Field(..., min_length=1, max_length=settings.PROMPT_MAX_LENGTH, description="Текст игрока")

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return clean_input(value)  # то же в пайплайне и в журнале попыток; NUL БД не принимает


class PredictResponse(BaseModel):
    text: str = Field(..., description="Ответ сервиса (пустая строка, если слово угадано)")
    passed: bool = Field(..., description="True — игрок ввёл слово-якорь и прошёл уровень")
