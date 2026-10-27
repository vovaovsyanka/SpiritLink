"""
Бэкенд на llama.cpp: на старте сервиса поднимает по процессу llama-server на каждую модель и говорит с ними
по OpenAI-совместимому API. Интернет не нужен: берутся только локальные файлы (models/llm/*.gguf, tools/llama.cpp).

Модели запускаются по одной (так на старте не борются за видеопамять и диск), сервис начинает принимать запросы,
когда все они готовы. Если запуск модели не удался, сервис продолжает работу без неё (недоступны её ступени).
"""

import asyncio
import atexit
import json
import logging
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import httpx

from app import settings

from .backend import Generation, GenerationBackend, LLMBusy, LLMError, strip_thinking
from .specs import MODELS, ModelSpec

logger = logging.getLogger(__name__)

PID_FILE = settings.LOGS_DIR / "llama" / "pids.json"
_EXE = "llama-server.exe" if sys.platform == "win32" else "llama-server"


def find_llama_server() -> Path | None:
    """LLAMA_SERVER_PATH → tools/llama.cpp → PATH."""
    if settings.LLAMA_SERVER_PATH and Path(settings.LLAMA_SERVER_PATH).is_file():
        return Path(settings.LLAMA_SERVER_PATH)
    if settings.TOOLS_DIR.is_dir():
        for path in settings.TOOLS_DIR.rglob(_EXE):
            return path
    found = shutil.which("llama-server")
    return Path(found) if found else None


def kill_orphans() -> None:
    """Гасит llama-server, оставшиеся от прошлого запуска (сервис упал и не успел их остановить)."""
    if not PID_FILE.is_file():
        return
    try:
        import psutil

        for pid in json.loads(PID_FILE.read_text(encoding="utf-8")):
            try:
                proc = psutil.Process(pid)
                if proc.name().lower().startswith("llama-server"):
                    logger.warning("Останавливаю забытый llama-server (pid %s)", pid)
                    proc.kill()
            except psutil.Error:
                pass
    except Exception:
        logger.warning("Не удалось проверить забытые процессы llama-server", exc_info=True)
    PID_FILE.unlink(missing_ok=True)


def _save_pids(pids: list[int]) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps(pids), encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LlamaServer:
    """Один процесс llama-server под одну модель."""

    def __init__(self, spec: ModelSpec, binary: Path):
        self.spec = spec
        self.slots = settings.LLAMA_SLOTS or spec.slots
        if not spec.path.is_file():
            raise FileNotFoundError(
                f"Нет файла модели {spec.path}. Выполните при включённом интернете: python scripts/download_models.py"
            )
        self.log_path = settings.LOGS_DIR / "llama" / f"{spec.key}.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        self.base_url = f"http://127.0.0.1:{port}"
        self._log = self.log_path.open("w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(self._command(binary, port), stdout=self._log, stderr=subprocess.STDOUT)

    def _command(self, binary: Path, port: int) -> list[str]:
        args = [str(binary), "-m", str(self.spec.path), "--host", "127.0.0.1", "--port", str(port),
                "-c", str(self.spec.ctx_per_slot * self.slots), "-np", str(self.slots), "--jinja", *self.spec.extra_args]
        if settings.LLAMA_GPU_LAYERS:
            args += ["-ngl", settings.LLAMA_GPU_LAYERS]
        return args + shlex.split(settings.LLAMA_EXTRA_ARGS)

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def log_tail(self, lines: int = 25) -> str:
        self._log.flush()
        return "\n".join(self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

    async def wait_ready(self, client: httpx.AsyncClient) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.LLAMA_START_TIMEOUT_SEC
        while loop.time() < deadline:
            if not self.alive:
                raise RuntimeError(f"llama-server завершился с кодом {self.proc.returncode}. Конец журнала:\n{self.log_tail()}")
            try:
                if (await client.get(self.base_url + "/health", timeout=5)).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
        raise RuntimeError(f"llama-server не запустился за {settings.LLAMA_START_TIMEOUT_SEC} с. Конец журнала:\n{self.log_tail()}")

    def stop(self) -> None:
        if self.alive:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self._log.close()


class LlamaCppBackend(GenerationBackend):
    name = "llamacpp"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC)
        self._servers: dict[str, LlamaServer] = {}
        self._limits: dict[str, asyncio.Semaphore] = {}
        self._failures: dict[str, str] = {}
        self._queued = 0
        atexit.register(self._stop_all)

    async def start(self, models: Iterable[str]) -> None:
        keys = list(models)
        binary = find_llama_server()
        if binary is None:
            raise RuntimeError(
                "Не найден llama-server. Выполните при включённом интернете: python scripts/download_models.py "
                "(или задайте LLAMA_SERVER_PATH)."
            )
        kill_orphans()
        for number, key in enumerate(keys, 1):
            logger.info("Запуск модели %s (%d из %d)...", key, number, len(keys))
            try:
                server = LlamaServer(MODELS[key], binary)
            except Exception as e:
                self._failures[key] = str(e)
                logger.error("Модель %s недоступна: %s", key, e)
                continue
            self._servers[key] = server
            _save_pids([s.proc.pid for s in self._servers.values()])
            try:
                await server.wait_ready(self._client)
            except Exception as e:
                self._failures[key] = str(e)
                self._servers.pop(key)
                server.stop()
                _save_pids([s.proc.pid for s in self._servers.values()])
                logger.error("Модель %s не запустилась: %s", key, e)
                continue
            self._limits[key] = asyncio.Semaphore(server.slots)
            logger.info("Модель %s готова (слотов: %d)", key, server.slots)

    async def aclose(self) -> None:
        await self._client.aclose()
        self._stop_all()

    def _stop_all(self) -> None:
        for server in self._servers.values():
            server.stop()
        self._servers.clear()
        PID_FILE.unlink(missing_ok=True)

    def is_available(self, model: str) -> bool:
        server = self._servers.get(model)
        return server is not None and server.alive

    def status(self) -> dict[str, str]:
        result = {key: "ready" if self.is_available(key) else "stopped" for key in self._servers}
        result.update({key: f"failed: {reason.splitlines()[0][:200]}" for key, reason in self._failures.items()})
        return result

    async def generate(
        self, model: str, system: str, user: str, *, max_tokens: int,
        temperature: float | None = None, purpose: str = "",
    ) -> Generation:
        if not self.is_available(model):
            raise LLMError(f"Модель {model} недоступна")
        limit = self._limits[model]
        if limit.locked() and self._queued >= settings.LLM_MAX_QUEUE:
            raise LLMBusy()

        self._queued += 1
        try:
            await limit.acquire()
        finally:
            self._queued -= 1
        try:
            return await self._post(self._servers[model], system, user, max_tokens, temperature)
        finally:
            limit.release()

    async def _post(
        self, server: LlamaServer, system: str, user: str, max_tokens: int, temperature: float | None
    ) -> Generation:
        payload = {
            "model": "local", "max_tokens": max_tokens, "top_p": settings.TOP_P,
            "temperature": settings.TEMPERATURE if temperature is None else temperature,
            "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": True,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            response = await self._client.post(server.base_url + "/v1/chat/completions", json=payload)
        except httpx.TimeoutException as e:
            raise LLMError(f"{server.spec.key}: превышено время ожидания") from e
        except httpx.HTTPError as e:
            raise LLMError(f"{server.spec.key}: нет связи с llama-server ({type(e).__name__})") from e
        if response.status_code >= 400:
            raise LLMError(f"{server.spec.key}: HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        usage = data.get("usage", {})
        text = strip_thinking(data["choices"][0]["message"].get("content") or "")
        return Generation(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
