"""Клиент Ollama API."""

import logging
from typing import Optional

import requests

from app import settings
from app.ghosts import GHOSTS

from .prompts import build_fallback_prompt, build_main_prompt

logger = logging.getLogger(__name__)

DEFAULT_GHOST_ID = 4


class LLMClient:
    """Отвечает на запросы пользователя голосом призрака, охраняющего пароль."""

    def __init__(self, model: Optional[str] = None):
        self.api_key = settings.OLLAMA_API_KEY
        self.model = model or settings.OLLAMA_MODEL
        self.api_url = settings.OLLAMA_API_URL
        self.last_eval_count = 0
        self._session = requests.Session()

    def _generate(self, prompt: str) -> dict:
        response = self._session.post(
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
            timeout=settings.LLM_TIMEOUT_SEC,
        )
        return response.json()

    def get_response(self, user_prompt: str, ghost_id: int, current_password: str = "") -> str:
        ghost = GHOSTS.get(ghost_id, GHOSTS[DEFAULT_GHOST_ID])
        history = ghost["llm_history"]

        try:
            data = self._generate(build_main_prompt(user_prompt, current_password, history))
            if data.get("eval_count") == settings.LLM_MAX_TOKENS:
                data = self._generate(build_fallback_prompt(current_password, history))

            self.last_eval_count = data.get("eval_count", 0)
            return data.get("response", "Ошибка: пустой ответ от модели").strip()

        except requests.exceptions.ConnectionError:
            return "Ошибка: не удалось подключиться к Ollama API. Проверьте подключение и URL."
        except requests.exceptions.Timeout:
            return "Ошибка: превышено время ожидания ответа от Ollama API."
        except Exception as e:
            logger.exception("Ошибка запроса к LLM")
            return f"Ошибка при обработке запроса: {e}"
