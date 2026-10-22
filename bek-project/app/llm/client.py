"""Асинхронный клиент Ollama API."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app import settings
from app.ghosts import GHOSTS

from .prompts import build_fallback_prompt, build_main_prompt

logger = logging.getLogger(__name__)

DEFAULT_GHOST_ID = 4


class LLMError(Exception):
    """Ollama вернула ошибку (неверный ключ, лимит, недоступная модель и т.п.)."""


@dataclass(frozen=True)
class LLMAnswer:
    text: str
    eval_count: int = 0


class LLMClient:
    """
    Отвечает на запросы пользователя голосом призрака, охраняющего пароль.

    Запросы неблокирующие: пока один игрок ждёт ответ модели, event loop свободен
    и обслуживает остальных. Число одновременных обращений к Ollama ограничено
    семафором (LLM_MAX_CONCURRENCY), чтобы не упереться в лимиты API.
    """

    def __init__(self, model: Optional[str] = None):
        self.api_key = settings.OLLAMA_API_KEY
        self.model = model or settings.OLLAMA_MODEL
        self.api_url = settings.OLLAMA_API_URL
        self._client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC)
        self._limiter = asyncio.Semaphore(settings.LLM_MAX_CONCURRENCY)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _generate(self, prompt: str) -> dict:
        async with self._limiter:
            response = await self._client.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": settings.LLM_MAX_TOKENS},
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )

        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code >= 400:
            raise LLMError(f"HTTP {response.status_code}: {data.get('error', response.text[:200])}")
        return data

    async def generate_answer(self, user_prompt: str, ghost_id: int, current_password: str = "") -> LLMAnswer:
        """Ответ модели; исключения (сеть, таймаут, LLMError) пробрасываются вызывающему."""
        history = GHOSTS.get(ghost_id, GHOSTS[DEFAULT_GHOST_ID])["llm_history"]

        data = await self._generate(build_main_prompt(user_prompt, current_password, history))
        if data.get("eval_count") == settings.LLM_MAX_TOKENS:
            data = await self._generate(build_fallback_prompt(current_password, history))

        text = data.get("response", "").strip() or "Ошибка: пустой ответ от модели"
        return LLMAnswer(text=text, eval_count=data.get("eval_count", 0))

    async def get_response(self, user_prompt: str, ghost_id: int, current_password: str = "") -> str:
        """Как generate_answer, но ошибки возвращаются текстом — игрок всегда получает ответ."""
        try:
            return (await self.generate_answer(user_prompt, ghost_id, current_password)).text
        except httpx.TimeoutException:
            return "Ошибка: превышено время ожидания ответа от Ollama API."
        except httpx.ConnectError:
            return "Ошибка: не удалось подключиться к Ollama API. Проверьте подключение и URL."
        except LLMError as e:
            logger.error("Ollama API: %s", e)
            return "Ошибка: модель сейчас недоступна, попробуйте позже."
        except Exception:
            logger.exception("Ошибка запроса к LLM")
            return "Ошибка при обработке запроса, попробуйте позже."
