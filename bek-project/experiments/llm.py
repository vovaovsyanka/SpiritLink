"""
Запуск моделей через llama.cpp.

  download_model(spec)  — скачивает GGUF с Hugging Face (докачивается после обрыва) и возвращает путь к файлу
  setup_llama_cpp()     — скачивает готовую сборку llama.cpp для Windows (llama-server)
  LlamaServer(spec)     — поднимает llama-server под модель; generate_batch(...) отправляет запросы; close() останавливает

Слои, не поместившиеся в видеопамять, llama.cpp держит в оперативной памяти, поэтому подходят и крупные модели.
Токен Hugging Face берётся из HF_TOKEN, experiments/.env или `hf auth login` (для открытых репозиториев не обязателен).
"""

import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import requests

import config
from config import ModelSpec

log = logging.getLogger("llm")

_SKIP_IN_NAME = ("mmproj", "imatrix", "eagle", "bf16/")
_FALLBACK_QUANTS = ("Q4_K_M", "Q4_K_XL", "Q4_K_S", "Q4_0", "IQ4_XS", "MXFP4", "Q5_K_M", "Q8_0")
_SHARD = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)


# ── скачивание ───────────────────────────────────────────────────────────────
def pick_gguf_files(files: list[str], quant: str) -> list[str]:
    """Из файлов репозитория выбирает один квант: единственный файл или все его части по порядку."""
    ggufs = [f for f in files if f.lower().endswith(".gguf") and not any(s in f.lower() for s in _SKIP_IN_NAME)]
    for pref in (quant, *_FALLBACK_QUANTS):
        matched = [f for f in ggufs if pref.lower() in f.lower()]
        singles = [f for f in matched if not _SHARD.search(f)]
        if singles:
            return [min(singles, key=len)]
        first = sorted(f for f in matched if (m := _SHARD.search(f)) and m.group(1) == "00001")
        if first:
            prefix = _SHARD.sub("", first[0])
            return sorted(f for f in matched if _SHARD.sub("", f) == prefix)
    return []


def download_model(spec: ModelSpec) -> Path:
    """Скачивает веса модели и возвращает путь к первому (или единственному) .gguf-файлу."""
    from huggingface_hub import HfApi, hf_hub_download

    files = HfApi().list_repo_files(spec.repo, token=config.HF_TOKEN)
    chosen = pick_gguf_files(files, spec.quant)
    if not chosen:
        raise RuntimeError(f"В {spec.repo} не найден квант {spec.quant}. Файлы: {[f for f in files if f.endswith('.gguf')][:20]}")
    print(f"  {spec.key}: {spec.repo} → {', '.join(chosen)}")
    return Path([hf_hub_download(spec.repo, filename=f, token=config.HF_TOKEN) for f in chosen][0])


def find_llama_server() -> Path | None:
    """LLAMA_SERVER_PATH → experiments/tools/llama.cpp → PATH."""
    env = os.getenv("LLAMA_SERVER_PATH")
    if env and Path(env).is_file():
        return Path(env)
    exe = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    if config.TOOLS_DIR.is_dir():
        for path in config.TOOLS_DIR.rglob(exe):
            return path
    found = shutil.which("llama-server")
    return Path(found) if found else None


def setup_llama_cpp(variant: str = "cuda-12.4") -> Path:
    """Скачивает и распаковывает llama.cpp (Windows) в experiments/tools/llama.cpp. Возвращает путь к llama-server."""
    if sys.platform != "win32":
        raise RuntimeError("Автоматическая установка рассчитана на Windows: поставьте llama.cpp сами и задайте LLAMA_SERVER_PATH.")
    releases = requests.get("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20", timeout=60).json()
    main_re = re.compile(rf"^llama-b\d+-bin-win-{re.escape(variant)}-x64\.zip$")
    cudart_re = re.compile(rf"^cudart-llama-bin-win-{re.escape(variant)}-x64\.zip$")
    for release in releases:
        assets = release.get("assets", [])
        main = next((a for a in assets if main_re.match(a["name"])), None)
        if main:
            break
    else:
        raise RuntimeError("Не нашёл сборку llama.cpp для Windows. Скачайте вручную: https://github.com/ggml-org/llama.cpp/releases")
    target = config.TOOLS_DIR / "llama.cpp"
    target.mkdir(parents=True, exist_ok=True)
    for asset in (main, next((a for a in assets if cudart_re.match(a["name"])), None)):
        if not asset:
            continue
        print(f"  скачиваю {asset['name']} ({asset['size'] / 1e6:.0f} МБ)")
        archive = target / asset["name"]
        with requests.get(asset["browser_download_url"], stream=True, timeout=60) as resp, archive.open("wb") as f:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
        archive.unlink()
    server = find_llama_server()
    if not server:
        raise RuntimeError(f"Распаковано в {target}, но llama-server.exe не найден")
    return server


# ── сервер ───────────────────────────────────────────────────────────────────
@dataclass
class GenResult:
    text: str
    prompt_tokens: int = 0
    new_tokens: int = 0
    latency: float = 0.0   # секунд на запрос


def strip_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return text.split("</think>")[-1].strip()


class LlamaServer:
    """llama-server под одну модель; запросы идут по OpenAI-совместимому API."""

    def __init__(self, spec: ModelSpec):
        server = find_llama_server()
        if server is None:
            raise RuntimeError("Не найден llama-server. Выполните `python run_experiments.py download` или задайте LLAMA_SERVER_PATH.")
        self.spec = spec
        self.slots = max(1, spec.batch_size)
        model_path = download_model(spec)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        args = [str(server), "-m", str(model_path), "--host", "127.0.0.1", "--port", str(port),
                "-c", str(spec.ctx_per_slot * self.slots), "-np", str(self.slots), "--jinja", *spec.extra_args]

        config.LLAMA_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = config.LLAMA_LOG_DIR / f"{spec.key}.log"
        self._log = self.log_path.open("w", encoding="utf-8", errors="replace")
        log.info("%s: запуск llama-server, журнал: %s", spec.key, self.log_path)
        self.proc = subprocess.Popen(args, stdout=self._log, stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{port}"
        self.session = requests.Session()
        try:
            self._wait_ready()
        except Exception:
            self.close()
            raise

    def _wait_ready(self) -> None:
        deadline = time.time() + config.LLAMA_START_TIMEOUT_SEC
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server завершился с кодом {self.proc.returncode}. Конец журнала:\n{self._log_tail()}")
            try:
                if self.session.get(self.base + "/health", timeout=5).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(2)
        raise RuntimeError(f"llama-server не запустился за {config.LLAMA_START_TIMEOUT_SEC} с. Конец журнала:\n{self._log_tail()}")

    def _log_tail(self, lines: int = 25) -> str:
        self._log.flush()
        return "\n".join(self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

    def _one(self, system: str, user: str, max_new_tokens: int, seed: int, temperature: float | None) -> GenResult:
        template_kwargs = {"enable_thinking": False}
        if self.spec.reasoning:  # у gpt-oss рассуждение отключить нельзя: минимальный уровень и запас токенов
            template_kwargs["reasoning_effort"] = "low"
            max_new_tokens += config.REASONING_EXTRA_TOKENS
        payload = {
            "model": "local", "max_tokens": max_new_tokens, "top_p": config.TOP_P,
            "temperature": config.TEMPERATURE if temperature is None else temperature,
            "seed": seed, "chat_template_kwargs": template_kwargs, "cache_prompt": True,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        start = time.perf_counter()
        resp = self.session.post(self.base + "/v1/chat/completions", json=payload, timeout=1800)
        if resp.status_code >= 400:
            raise RuntimeError(f"Сервер вернул {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        usage = data.get("usage", {})
        text = strip_thinking(data["choices"][0]["message"]["content"] or "")
        return GenResult(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), time.perf_counter() - start)

    def generate_batch(self, items: list[tuple[str, str]], max_new_tokens: int, seed: int = 0, temperature: float | None = None) -> list[GenResult]:
        """items — пары (system, user); запросы выполняются параллельно в слотах сервера. temperature=None — config.TEMPERATURE."""
        with ThreadPoolExecutor(max_workers=self.slots) as pool:
            futures = [pool.submit(self._one, s, u, max_new_tokens, seed + i, temperature) for i, (s, u) in enumerate(items)]
            return [f.result() for f in futures]

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self._log.close()
