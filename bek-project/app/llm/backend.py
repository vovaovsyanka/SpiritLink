"""
Интерфейс генерации. Пайплайн знает только его, поэтому источник моделей меняется настройкой LLM_BACKEND:
llamacpp (свои процессы llama-server, работает без интернета) сейчас, Ollama на сервере — отдельным адаптером.

Новый адаптер: наследник GenerationBackend + строка в BACKENDS (app/llm/__init__.py).
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable


class LLMError(Exception):
    """Модель не ответила: ошибка сервера, таймаут, обрыв соединения."""


class LLMBusy(LLMError):
    """Очередь к модели переполнена; клиенту уходит 429 с Retry-After."""

    def __init__(self, retry_after: int = 5):
        super().__init__("Очередь к языковым моделям переполнена")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int = 0
    new_tokens: int = 0


def strip_thinking(text: str) -> str:
    """Убирает блок рассуждений <think>...</think>, если модель всё же его вывела."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return text.split("</think>")[-1].strip()


class GenerationBackend(ABC):
    name: str = ""

    @abstractmethod
    async def start(self, models: Iterable[str]) -> None:
        """Подготавливает модели (ключи из app/llm/specs.py). Модель, которую не удалось запустить, помечается недоступной."""

    @abstractmethod
    async def aclose(self) -> None:
        ...

    @abstractmethod
    def is_available(self, model: str) -> bool:
        ...

    @abstractmethod
    def status(self) -> dict[str, str]:
        """Состояние моделей для /health: ключ → ready | failed: причина | stopped."""

    @abstractmethod
    async def generate(
        self, model: str, system: str, user: str, *, max_tokens: int,
        temperature: float | None = None, purpose: str = "",
    ) -> Generation:
        """purpose (classifier | mini | defender) нужен логам и заглушке; temperature=None — settings.TEMPERATURE."""
