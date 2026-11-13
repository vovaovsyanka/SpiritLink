"""
Бэкенд для LLM-сервиса сервера (Ollama за шлюзом VM Panel): LLM_BACKEND=ollama.

На ВМ нет видеокарты, поэтому модели работают на GPU сервера, а приложение ходит к ним по HTTP в формате OpenAI
(POST {OPENAI_BASE_URL}/chat/completions с ключом ВМ). Адрес и ключ панель сама записывает на ВМ в
/etc/vmpanel-llm.env; в compose этот файл подключается к контейнеру приложения.

Что здесь важного:
  * шлюз пускает от ВМ ограниченное число запросов одновременно (OLLAMA_CONCURRENCY): лишние ждём у себя,
    а не получаем от шлюза 429; если очередь выросла выше LLM_MAX_QUEUE, игроку уходит 429 (LLMBusy);
  * Ollama выгружает модель из видеопамяти через 30 минут простоя, а первый запрос после этого ждёт загрузки.
    Поэтому на старте модели «прогреваются» и затем раз в OLLAMA_KEEPALIVE_SEC получают короткий запрос;
  * рассуждения (thinking) отключены: reasoning_effort="none".
"""

import asyncio
import contextlib
import logging
from typing import Iterable

import httpx

from app import settings

from .backend import Generation, GenerationBackend, LLMBusy, LLMError, strip_thinking
from .specs import MODELS

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 502, 503}


class LLMHTTPError(LLMError):
    def __init__(self, model: str, status_code: int, body: str, retry_after: int = 0):
        super().__init__(f"{model}: HTTP {status_code}: {body[:300]}")
        self.status_code = status_code
        self.retry_after = retry_after


class OllamaBackend(GenerationBackend):
    name = "ollama"

    def __init__(self):
        if not settings.OPENAI_BASE_URL:
            raise RuntimeError(
                "Не задан OPENAI_BASE_URL. На сервере его записывает панель в /etc/vmpanel-llm.env "
                "(администратор включает ВМ доступ к LLM-сервису)."
            )
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"} if settings.OPENAI_API_KEY else {}
        self._client = httpx.AsyncClient(
            base_url=settings.OPENAI_BASE_URL, headers=headers, timeout=settings.LLM_TIMEOUT_SEC
        )
        self._limit = asyncio.Semaphore(max(1, settings.OLLAMA_CONCURRENCY))
        self._names: dict[str, str] = {}        # наш ключ → имя в Ollama (только готовые модели)
        self._failures: dict[str, str] = {}
        self._queued = 0
        self._keepalive: asyncio.Task | None = None

    # ── Запуск и остановка ───────────────────────────────────────────────────
    async def start(self, models: Iterable[str]) -> None:
        keys = list(models)
        try:
            response = await self._client.get("/models")
            response.raise_for_status()
            served = {item["id"] for item in response.json().get("data", [])}
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise RuntimeError(f"LLM-сервис недоступен ({settings.OPENAI_BASE_URL}): {e}") from e

        for key in keys:
            name = MODELS[key].ollama_name
            if name in served or f"{name}:latest" in served:
                self._names[key] = name if name in served else f"{name}:latest"
            else:
                self._failures[key] = f"в LLM-сервисе нет модели {name} (попросите администратора загрузить)"
                logger.error("Модель %s недоступна: %s", key, self._failures[key])

        if settings.OLLAMA_WARMUP:
            for number, key in enumerate(list(self._names), 1):
                logger.info("Прогрев модели %s (%d из %d)...", key, number, len(self._names))
                await self._warm(key)
        if settings.OLLAMA_KEEPALIVE_SEC > 0 and self._names:
            self._keepalive = asyncio.create_task(self._keep_warm())

    async def _warm(self, key: str) -> None:
        try:
            await self.generate(key, "Ответь одним словом.", "Привет", max_tokens=1, temperature=0.0, purpose="warmup")
        except LLMHTTPError as e:
            if e.status_code in _RETRY_STATUSES:    # шлюз занят: модель не сломана
                logger.warning("Прогрев %s не удался: %s", key, e)
                return
            self._names.pop(key, None)
            self._failures[key] = str(e)
            logger.error("Модель %s не отвечает: %s", key, e)
        except LLMError as e:
            logger.warning("Прогрев %s не удался: %s", key, e)

    async def _keep_warm(self) -> None:
        while True:
            await asyncio.sleep(settings.OLLAMA_KEEPALIVE_SEC)
            for key in list(self._names):
                with contextlib.suppress(LLMError):
                    await self.generate(key, "Ответь одним словом.", "Привет", max_tokens=1, temperature=0.0, purpose="warmup")

    async def aclose(self) -> None:
        if self._keepalive:
            self._keepalive.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._keepalive
        await self._client.aclose()

    # ── Состояние ────────────────────────────────────────────────────────────
    def is_available(self, model: str) -> bool:
        return model in self._names

    def status(self) -> dict[str, str]:
        result = {key: "ready" for key in self._names}
        result.update({key: f"failed: {reason.splitlines()[0][:200]}" for key, reason in self._failures.items()})
        return result

    # ── Генерация ────────────────────────────────────────────────────────────
    async def generate(
        self, model: str, system: str, user: str, *, max_tokens: int,
        temperature: float | None = None, purpose: str = "",
    ) -> Generation:
        if not self.is_available(model):
            raise LLMError(f"Модель {model} недоступна")
        if self._limit.locked() and self._queued >= settings.LLM_MAX_QUEUE:
            raise LLMBusy()

        self._queued += 1
        try:
            await self._limit.acquire()
        finally:
            self._queued -= 1
        try:
            return await self._post_with_retries(model, system, user, max_tokens, temperature)
        finally:
            self._limit.release()

    async def _post_with_retries(
        self, model: str, system: str, user: str, max_tokens: int, temperature: float | None
    ) -> Generation:
        for attempt in range(1, settings.OLLAMA_RETRIES + 1):
            try:
                return await self._post(model, system, user, max_tokens, temperature)
            except LLMHTTPError as e:
                if e.status_code not in _RETRY_STATUSES:
                    raise
                if attempt == settings.OLLAMA_RETRIES:
                    if e.status_code == 429:    # лимит шлюза: клиенту «сервер занят, попробуйте позже»
                        raise LLMBusy(retry_after=e.retry_after or 5) from e
                    raise
                delay = e.retry_after or 2 * attempt
                logger.warning("%s: HTTP %d, повтор %d через %d с", model, e.status_code, attempt, delay)
                await asyncio.sleep(delay)
        raise AssertionError("недостижимо")

    async def _post(
        self, model: str, system: str, user: str, max_tokens: int, temperature: float | None
    ) -> Generation:
        payload = {
            "model": self._names[model], "max_tokens": max_tokens, "top_p": settings.TOP_P,
            "temperature": settings.TEMPERATURE if temperature is None else temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if settings.OLLAMA_REASONING_EFFORT:
            payload["reasoning_effort"] = settings.OLLAMA_REASONING_EFFORT
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as e:
            raise LLMError(f"{model}: превышено время ожидания") from e
        except httpx.HTTPError as e:
            raise LLMError(f"{model}: нет связи с LLM-сервисом ({type(e).__name__})") from e
        if response.status_code >= 400:
            retry_after = response.headers.get("Retry-After", "")
            raise LLMHTTPError(model, response.status_code, response.text, int(retry_after) if retry_after.isdigit() else 0)

        data = response.json()
        usage = data.get("usage") or {}
        text = strip_thinking(data["choices"][0]["message"].get("content") or "")
        return Generation(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
