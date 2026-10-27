"""
Бэкенд llama.cpp: запуск процессов, готовность, слоты, очередь, сбои, остановка.
Вместо llama-server запускается tests/fake_llama_server.py (тот же HTTP-интерфейс), поэтому тесты быстрые и без моделей.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
import psutil
import pytest

from app import settings
from app.llm import llamacpp
from app.llm.backend import LLMBusy, LLMError
from app.llm.llamacpp import LlamaCppBackend, LlamaServer, kill_orphans
from app.llm.specs import MODELS, required_models

FAKE = Path(__file__).with_name("fake_llama_server.py")
KEYS = ["yandexgpt5-lite-8b", "qwen3-4b"]


@pytest.fixture
def fake_llama(tmp_path, monkeypatch):
    """Подменяет llama-server поддельным, а папки моделей и журналов — временными."""
    llm_dir = tmp_path / "llm"
    llm_dir.mkdir()
    for key in MODELS:
        (llm_dir / f"{key}.gguf").write_bytes(b"gguf")
    monkeypatch.setattr(settings, "LLM_DIR", llm_dir)
    monkeypatch.setattr(settings, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(llamacpp, "PID_FILE", tmp_path / "logs" / "llama" / "pids.json")
    monkeypatch.setattr(llamacpp, "find_llama_server", lambda: Path(sys.executable))
    monkeypatch.setattr(
        LlamaServer, "_command",
        lambda self, binary, port: [sys.executable, str(FAKE), "--port", str(port), "--key", self.spec.key],
    )
    monkeypatch.setattr(settings, "LLAMA_START_TIMEOUT_SEC", 20)
    return tmp_path


@pytest.fixture
async def backend(fake_llama):
    backend = LlamaCppBackend()
    yield backend
    await backend.aclose()


async def server_stats(backend, key) -> dict:
    async with httpx.AsyncClient() as client:
        return (await client.get(backend._servers[key].base_url + "/stats")).json()


async def test_start_makes_every_model_ready(backend):
    await backend.start(KEYS)
    assert backend.status() == {key: "ready" for key in KEYS}
    assert all(backend.is_available(key) for key in KEYS)
    assert not backend.is_available("gemma4-12b")


async def test_generate_returns_text_without_thinking_and_token_counts(backend):
    await backend.start(KEYS)
    result = await backend.generate("qwen3-4b", "система", "привет", max_tokens=10)
    assert result.text == "эхо[qwen3-4b]: привет"          # блок <think> убран
    assert result.new_tokens == 5 and result.prompt_tokens == len("привет")


async def test_models_get_slots_from_spec_and_env_override(backend, monkeypatch):
    await backend.start(["qwen3-4b", "gemma4-12b"])
    assert backend._servers["qwen3-4b"].slots == MODELS["qwen3-4b"].slots
    assert backend._servers["gemma4-12b"].slots == MODELS["gemma4-12b"].slots
    monkeypatch.setattr(settings, "LLAMA_SLOTS", 1)
    other = LlamaCppBackend()
    await other.start(["qwen3-4b"])
    assert other._servers["qwen3-4b"].slots == 1
    await other.aclose()


async def test_concurrency_never_exceeds_slots(backend, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_DELAY", "0.3")
    monkeypatch.setattr(settings, "LLAMA_SLOTS", 2)
    monkeypatch.setattr(settings, "LLM_MAX_QUEUE", 100)
    await backend.start(["qwen3-4b"])
    results = await asyncio.gather(*(backend.generate("qwen3-4b", "s", f"q{i}", max_tokens=5) for i in range(6)))
    assert len(results) == 6
    stats = await server_stats(backend, "qwen3-4b")
    assert stats["total"] == 6 and stats["max_concurrent"] == 2


async def test_parallel_requests_to_different_models_do_not_wait_for_each_other(backend, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_DELAY", "0.4")
    await backend.start(KEYS)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await asyncio.gather(*(backend.generate(key, "s", "q", max_tokens=5) for key in KEYS))
    assert loop.time() - start < 0.75


async def test_full_queue_raises_busy_and_the_rest_succeed(backend, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_DELAY", "0.3")
    monkeypatch.setattr(settings, "LLAMA_SLOTS", 1)
    monkeypatch.setattr(settings, "LLM_MAX_QUEUE", 2)
    await backend.start(["qwen3-4b"])
    results = await asyncio.gather(
        *(backend.generate("qwen3-4b", "s", f"q{i}", max_tokens=5) for i in range(8)), return_exceptions=True
    )
    busy = [r for r in results if isinstance(r, LLMBusy)]
    done = [r for r in results if not isinstance(r, Exception)]
    assert len(done) == 3 and len(busy) == 5                       # 1 в работе + 2 в очереди
    assert backend._queued == 0                                    # счётчик очереди не «протекает»
    assert (await backend.generate("qwen3-4b", "s", "после", max_tokens=5)).text.endswith("после")


async def test_model_that_exits_at_start_is_failed_and_others_work(backend, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_FAIL", "qwen3-4b")
    await backend.start(KEYS)
    assert backend.status()["yandexgpt5-lite-8b"] == "ready"
    assert backend.status()["qwen3-4b"].startswith("failed")
    assert not backend.is_available("qwen3-4b")
    with pytest.raises(LLMError):
        await backend.generate("qwen3-4b", "s", "q", max_tokens=5)


async def test_missing_gguf_file_marks_model_failed_with_hint(backend, fake_llama):
    (fake_llama / "llm" / "qwen3-4b.gguf").unlink()
    await backend.start(KEYS)
    assert "download_models" in backend.status()["qwen3-4b"]
    assert backend.is_available("yandexgpt5-lite-8b")


async def test_missing_llama_server_binary_stops_startup(backend, monkeypatch):
    monkeypatch.setattr(llamacpp, "find_llama_server", lambda: None)
    with pytest.raises(RuntimeError, match="llama-server"):
        await backend.start(KEYS)


async def test_start_waits_while_model_is_loading(backend, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_LOAD", "1.2")                  # /health отвечает 503, пока «грузится»
    loop = asyncio.get_running_loop()
    start = loop.time()
    await backend.start(["qwen3-4b"])
    assert loop.time() - start >= 1.0 and backend.is_available("qwen3-4b")


async def test_start_timeout_marks_model_failed(backend, monkeypatch):
    monkeypatch.setenv("FAKE_LLAMA_LOAD", "30")
    monkeypatch.setattr(settings, "LLAMA_START_TIMEOUT_SEC", 2)
    await backend.start(["qwen3-4b"])
    assert "не запустился" in backend.status()["qwen3-4b"] and not backend.is_available("qwen3-4b")


async def test_process_dying_later_makes_model_unavailable(backend):
    await backend.start(KEYS)
    backend._servers["qwen3-4b"].proc.kill()
    backend._servers["qwen3-4b"].proc.wait()
    assert not backend.is_available("qwen3-4b") and backend.is_available("yandexgpt5-lite-8b")
    with pytest.raises(LLMError, match="недоступна"):
        await backend.generate("qwen3-4b", "s", "q", max_tokens=5)


async def test_server_error_becomes_llm_error(backend):
    await backend.start(["qwen3-4b"])
    server = backend._servers["qwen3-4b"]
    server.base_url = "http://127.0.0.1:1"                           # никто не слушает
    with pytest.raises(LLMError):
        await backend.generate("qwen3-4b", "s", "q", max_tokens=5)


async def test_aclose_stops_every_process_and_removes_pid_file(fake_llama):
    backend = LlamaCppBackend()
    await backend.start(KEYS)
    procs = [s.proc for s in backend._servers.values()]
    assert llamacpp.PID_FILE.is_file() and len(json.loads(llamacpp.PID_FILE.read_text())) == 2
    await backend.aclose()
    assert all(p.poll() is not None for p in procs)
    assert not llamacpp.PID_FILE.exists()


async def test_pid_file_lists_running_servers(backend):
    await backend.start(KEYS)
    pids = json.loads(llamacpp.PID_FILE.read_text())
    assert sorted(pids) == sorted(s.proc.pid for s in backend._servers.values())


def test_kill_orphans_does_not_touch_unrelated_processes(fake_llama):
    """В pid-файле может остаться номер, который система отдала другой программе: чужие процессы не убиваем."""
    stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        llamacpp.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        llamacpp.PID_FILE.write_text(json.dumps([stranger.pid, 999999]))
        kill_orphans()
        assert stranger.poll() is None
        assert not llamacpp.PID_FILE.exists()
    finally:
        stranger.kill()


def test_kill_orphans_without_pid_file_is_noop(fake_llama):
    kill_orphans()


def test_kill_orphans_kills_leftover_llama_server(fake_llama, tmp_path):
    """Процесс с именем llama-server (после аварии сервиса) гасится при следующем старте."""
    exe = tmp_path / ("llama-server.exe" if sys.platform == "win32" else "llama-server")
    exe.write_bytes(Path(sys.executable).read_bytes())
    if sys.platform != "win32":
        exe.chmod(0o755)
    orphan = subprocess.Popen([str(exe), "-c", "import time; time.sleep(60)"])
    try:
        assert psutil.Process(orphan.pid).name().lower().startswith("llama-server")
        llamacpp.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        llamacpp.PID_FILE.write_text(json.dumps([orphan.pid]))
        kill_orphans()
        assert orphan.wait(timeout=10) is not None
    finally:
        orphan.kill()


async def test_pipeline_create_with_llamacpp_backend(fake_llama, monkeypatch):
    """Весь старт сервиса на поддельных llama-server: четыре процесса, BERT-заглушка, ответы по ступеням."""
    from app.pipeline import ProcessingPipeline

    monkeypatch.setattr(settings, "STUB_MODELS", True)
    monkeypatch.setattr(settings, "STUB_LLM", False)
    pipeline = await ProcessingPipeline.create()
    try:
        assert pipeline.available_world_levels == [1, 2, 3, 4]
        assert set(pipeline.health()["models"]) == set(required_models())
        result = await pipeline.process("привет, как дела", 3, "ФЕНИКС", 2)
        assert result.text.startswith(f"эхо[{settings.SERVICE_MODEL}]") and result.trace["stages"][-1]["stage"] == "mini"
        assert (await pipeline.process("ФЕНИКС", 3, "ФЕНИКС", 2)).passed
    finally:
        await pipeline.aclose()
