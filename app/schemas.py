from typing import Literal

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    level: Literal["tony_stark", "subnautica", "cyberpunk"] = Field(
        ...,
        description="Игровой уровень: tony_stark (кат. 3), subnautica (кат. 4), cyberpunk (кат. 5)",
    )
    text: str = Field(..., min_length=1, description="Текст пользователя")


class PredictResponse(BaseModel):
    text: str = Field(..., description="Ответ сервиса (пустая строка, если пароль угадан)")
    passed: bool = Field(..., description="True — пользователь угадал пароль и прошёл уровень")
