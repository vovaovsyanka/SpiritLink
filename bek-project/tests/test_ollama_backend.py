"""
Бэкенд Ollama (app/llm/ollama.py): список моделей, запрос в формате OpenAI, повторы при 429, лимит одновременных запросов.
Настоящий LLM-сервис не нужен: httpx.MockTransport подменяет сеть.
"""

import asyncio
import json

import httpx
import pytest

from app import settings
from app.llm import LLMBusy, LLMError, create_backend
from app.llm.ollama import OllamaBackend
from app.llm.specs import MODELS

REAL_SLEEP = asyncio.sleep
QWEN = MODELS["qwen3-4b"].ollama_name
YANDEX = MODELS["yandexgpt5-lite-8b"].ollama_name


@pytest.fixture(autouse=True)
def _ollama_settings(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "secret-key")
    monkeypatch.setattr(settings, "OLLAMA_WARMUP", False)
    monkeypatch.setattr(settings, "OLLAMA_KEEPALIVE_SEC", 0)
    monkeypatch.setattr(settings, "OLLAMA_RETRIES", 3)
    monkeypatch.setattr(settings, "OLLAMA_CONCURRENCY", 2)


def make_backend(handler) -> OllamaBackend:
    backend = OllamaBackend()
    backend._client = httpx.AsyncClient(
        base_url=settings.OPENAI_BASE_URL, transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer secret-key"},
    )
    return backend


def reply(text="Привет", **extra) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}, **extra,
    })


def models_response(*names) -> httpx.Response:
    return httpx.Response(200, json={"object": "list", "data": [{"id": n} for n in names]})


async def test_start_marks_only_served_models_ready():
    backend = make_backend(lambda request: models_response(QWEN, f"{YANDEX}:latest"))
    await backend.start(["qwen3-4b", "yandexgpt5-lite-8b", "gemma4-12b"])

    assert backend.is_available("qwen3-4b")
    assert backend.is_available("yandexgpt5-lite-8b")      # в списке сервиса с суффиксом :latest
    assert not backend.is_available("gemma4-12b")
    status = backend.status()
    assert status["qwen3-4b"] == "ready"
    assert status["gemma4-12b"].startswith("failed: в LLM-сервисе нет модели")
    await backend.aclose()


async def test_start_fails_when_service_unreachable():
    def down(request):
        raise httpx.ConnectError("нет связи")

    backend = make_backend(down)
    with pytest.raises(RuntimeError, match="LLM-сервис недоступен"):
        await backend.start(["qwen3-4b"])
    await backend.aclose()


async def test_generate_sends_openai_request_and_parses_answer():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return models_response(QWEN)
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return reply("<think>скрытые мысли</think>Ответ призрака")

    backend = make_backend(handler)
    await backend.start(["qwen3-4b"])
    generation = await backend.generate("qwen3-4b", "системный", "пользовательский", max_tokens=50, temperature=0.0)

    assert generation.text == "Ответ призрака"             # блок рассуждений вырезан
    assert (generation.prompt_tokens, generation.new_tokens) == (7, 3)
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    body = seen["body"]
    assert body["model"] == QWEN
    assert body["max_tokens"] == 50 and body["temperature"] == 0.0
    assert body["reasoning_effort"] == "none"
    assert body["messages"] == [{"role": "system", "content": "системный"}, {"role": "user", "content": "пользовательский"}]
    await backend.aclose()


async def test_unknown_model_is_unavailable():
    backend = make_backend(lambda request: models_response())
    await backend.start(["qwen3-4b"])
    with pytest.raises(LLMError, match="недоступна"):
        await backend.generate("qwen3-4b", "s", "u", max_tokens=5)
    await backend.aclose()


async def test_retries_on_429_and_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.llm.ollama.asyncio.sleep", lambda delay: REAL_SLEEP(0))
    calls = []

    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response(QWEN)
        calls.append(1)
        return httpx.Response(429, text="busy") if len(calls) < 3 else reply("ок")

    backend = make_backend(handler)
    await backend.start(["qwen3-4b"])
    assert (await backend.generate("qwen3-4b", "s", "u", max_tokens=5)).text == "ок"
    assert len(calls) == 3
    await backend.aclose()


async def test_429_after_all_retries_becomes_llm_busy(monkeypatch):
    monkeypatch.setattr("app.llm.ollama.asyncio.sleep", lambda delay: REAL_SLEEP(0))

    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response(QWEN)
        return httpx.Response(429, headers={"Retry-After": "7"}, text="лимит")

    backend = make_backend(handler)
    await backend.start(["qwen3-4b"])
    with pytest.raises(LLMBusy) as error:
        await backend.generate("qwen3-4b", "s", "u", max_tokens=5)
    assert error.value.retry_after == 7
    await backend.aclose()


async def test_client_error_is_not_retried():
    calls = []

    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response(QWEN)
        calls.append(1)
        return httpx.Response(404, text="model not found")

    backend = make_backend(handler)
    await backend.start(["qwen3-4b"])
    with pytest.raises(LLMError, match="HTTP 404"):
        await backend.generate("qwen3-4b", "s", "u", max_tokens=5)
    assert len(calls) == 1
    await backend.aclose()


async def test_warmup_disables_broken_model_but_keeps_busy_one(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_WARMUP", True)
    monkeypatch.setattr(settings, "OLLAMA_RETRIES", 1)

    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response(QWEN, YANDEX)
        model = json.loads(request.content)["model"]
        return httpx.Response(500, text="не поддерживается") if model == QWEN else httpx.Response(503, text="перезапуск")

    backend = make_backend(handler)
    await backend.start(["qwen3-4b", "yandexgpt5-lite-8b"])
    assert not backend.is_available("qwen3-4b")          # ошибка сервера 500: модель не работает
    assert "HTTP 500" in backend.status()["qwen3-4b"]
    assert backend.is_available("yandexgpt5-lite-8b")    # 503 бывает при перезапуске шлюза, модель оставляем
    await backend.aclose()


async def test_concurrency_is_limited_to_gateway_limit(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_CONCURRENCY", 2)
    running = peak = 0

    async def slow_transport(request: httpx.Request) -> httpx.Response:
        nonlocal running, peak
        if request.url.path.endswith("/models"):
            return models_response(QWEN)
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        return reply()

    backend = OllamaBackend()
    backend._client = httpx.AsyncClient(base_url=settings.OPENAI_BASE_URL, transport=httpx.MockTransport(slow_transport))
    await backend.start(["qwen3-4b"])
    await asyncio.gather(*(backend.generate("qwen3-4b", "s", "u", max_tokens=5) for _ in range(6)))
    assert peak == 2
    await backend.aclose()


async def test_queue_overflow_raises_llm_busy(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "LLM_MAX_QUEUE", 1)

    async def slow_transport(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return models_response(QWEN)
        await asyncio.sleep(0.1)
        return reply()

    backend = OllamaBackend()
    backend._client = httpx.AsyncClient(base_url=settings.OPENAI_BASE_URL, transport=httpx.MockTransport(slow_transport))
    await backend.start(["qwen3-4b"])
    tasks = [asyncio.create_task(backend.generate("qwen3-4b", "s", "u", max_tokens=5)) for _ in range(2)]
    await asyncio.sleep(0.01)           # один запрос выполняется, второй стоит в очереди
    with pytest.raises(LLMBusy):
        await backend.generate("qwen3-4b", "s", "u", max_tokens=5)
    await asyncio.gather(*tasks)
    await backend.aclose()


def test_base_url_is_required(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "")
    with pytest.raises(RuntimeError, match="OPENAI_BASE_URL"):
        OllamaBackend()


def test_create_backend_selects_ollama(monkeypatch):
    monkeypatch.setattr(settings, "STUB_LLM", False)
    monkeypatch.setattr(settings, "LLM_BACKEND", "ollama")
    assert isinstance(create_backend(), OllamaBackend)


def test_model_names_can_be_overridden(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MODELS", {"qwen3-4b": "qwen3:4b"})
    assert MODELS["qwen3-4b"].ollama_name == "qwen3:4b"
    assert MODELS["gemma4-12b"].ollama_name.startswith("hf.co/")
