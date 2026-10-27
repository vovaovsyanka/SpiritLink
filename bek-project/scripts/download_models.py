"""
Разовая подготовка файлов для работы сервиса без интернета. Выполняется при включённом интернете
(или на машине, где всё уже есть в кэше Hugging Face / в experiments/tools: тогда сеть не нужна).

  python scripts/download_models.py                  # всё: токенайзер BERT, llama.cpp, четыре языковые модели
  python scripts/download_models.py --only tokenizer # или llama, или models
  python scripts/download_models.py --llama-variant cuda-12.4

Результат (после этого сеть сервису больше не нужна):
  models/rosberta/          рядом с весами BERT появляются файлы токенайзера
  tools/llama.cpp/          llama-server (Windows; на другой системе поставьте llama.cpp сами и задайте LLAMA_SERVER_PATH)
  models/llm/<модель>.gguf  GGUF-файлы моделей из app/llm/specs.py
Веса самого BERT (models/rosberta/model.safetensors) скрипт не качает: они не публичные, их кладут вручную.
"""

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app import settings
from app.llm.llamacpp import find_llama_server
from app.llm.specs import MODELS, ModelSpec, required_models

BERT_TOKENIZER_REPO = "ai-forever/ru-en-RoSBERTa"
TOKENIZER_FILES = ["tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "special_tokens_map.json"]
SKIP_IN_NAME = ("mmproj", "imatrix", "eagle", "bf16/")
SHARD = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)


def _hub(func, *args, **kwargs):
    """Сначала кэш Hugging Face (без сети), если там нет нужного — скачивание."""
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        return func(*args, local_files_only=True, **kwargs)
    except (LocalEntryNotFoundError, OSError):
        return func(*args, **kwargs)


# ── токенайзер BERT ──────────────────────────────────────────────────────────
def prepare_tokenizer() -> None:
    from huggingface_hub import snapshot_download

    target = settings.GENERAL_BERT_PATH
    if (target / "tokenizer.json").is_file() or (target / "vocab.json").is_file():
        print(f"токенайзер: уже есть в {target}")
        return
    if not (target / "config.json").is_file():
        raise SystemExit(f"Нет {target / 'config.json'}: сначала положите туда веса BERT (config.json и model.safetensors).")
    snapshot = Path(_hub(snapshot_download, BERT_TOKENIZER_REPO, allow_patterns=TOKENIZER_FILES))
    copied = [name for name in TOKENIZER_FILES if (snapshot / name).is_file()]
    for name in copied:
        shutil.copy2(snapshot / name, target / name)
    print(f"токенайзер: скопировано {len(copied)} файлов в {target}")


# ── llama.cpp ────────────────────────────────────────────────────────────────
def prepare_llama(variant: str) -> None:
    server = find_llama_server()
    if server:
        print(f"llama.cpp: уже есть, {server}")
        return
    existing = PROJECT_DIR / "experiments" / "tools" / "llama.cpp"   # поставлен для экспериментов
    if existing.is_dir():
        shutil.copytree(existing, settings.TOOLS_DIR / "llama.cpp", dirs_exist_ok=True)
        print(f"llama.cpp: скопирован из {existing}")
        return
    if sys.platform != "win32":
        raise SystemExit("llama.cpp: автоматическая установка рассчитана на Windows. Поставьте llama.cpp сами и задайте LLAMA_SERVER_PATH.")

    import httpx

    releases = httpx.get("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20", timeout=60).json()
    main_re = re.compile(rf"^llama-b\d+-bin-win-{re.escape(variant)}-x64\.zip$")
    cudart_re = re.compile(rf"^cudart-llama-bin-win-{re.escape(variant)}-x64\.zip$")
    for release in releases:
        assets = release.get("assets", [])
        main = next((a for a in assets if main_re.match(a["name"])), None)
        if main:
            break
    else:
        raise SystemExit("llama.cpp: не нашёл сборку для Windows. Скачайте вручную: https://github.com/ggml-org/llama.cpp/releases")
    target = settings.TOOLS_DIR / "llama.cpp"
    target.mkdir(parents=True, exist_ok=True)
    for asset in (main, next((a for a in assets if cudart_re.match(a["name"])), None)):
        if not asset:
            continue
        print(f"llama.cpp: скачиваю {asset['name']} ({asset['size'] / 1e6:.0f} МБ)")
        archive = target / asset["name"]
        with httpx.stream("GET", asset["browser_download_url"], follow_redirects=True, timeout=60) as response, archive.open("wb") as f:
            response.raise_for_status()
            for chunk in response.iter_bytes(1 << 20):
                f.write(chunk)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
        archive.unlink()
    print(f"llama.cpp: установлен в {target}")


# ── языковые модели ──────────────────────────────────────────────────────────
def pick_gguf_files(files: list[str], quant: str) -> list[str]:
    """Из файлов репозитория выбирает один квант: единственный файл или все его части по порядку."""
    ggufs = [f for f in files if f.lower().endswith(".gguf") and not any(s in f.lower() for s in SKIP_IN_NAME)]
    matched = [f for f in ggufs if quant.lower() in f.lower()]
    singles = [f for f in matched if not SHARD.search(f)]
    return [min(singles, key=len)] if singles else []


def find_gguf(spec: ModelSpec) -> Path:
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download

    pattern = f"*{spec.quant}*.gguf"
    try:   # кэш Hugging Face без сети
        snapshot = Path(snapshot_download(spec.repo, allow_patterns=[pattern], local_files_only=True))
        local = pick_gguf_files([p.name for p in snapshot.glob("*.gguf")], spec.quant)
        if local:
            return snapshot / local[0]
    except OSError:
        pass
    files = HfApi().list_repo_files(spec.repo)
    chosen = pick_gguf_files(files, spec.quant)
    if not chosen:
        raise RuntimeError(f"В {spec.repo} не найден одиночный файл {spec.quant}. Файлы: {[f for f in files if f.endswith('.gguf')][:20]}")
    print(f"  {spec.key}: скачиваю {spec.repo} → {chosen[0]} (~{spec.size_gb} ГБ)")
    return Path(hf_hub_download(spec.repo, filename=chosen[0]))


def prepare_models() -> None:
    settings.LLM_DIR.mkdir(parents=True, exist_ok=True)
    for key in required_models():
        spec = MODELS[key]
        if spec.path.is_file() and spec.path.stat().st_size > 0:
            print(f"{key}: уже есть, {spec.path}")
            continue
        source = find_gguf(spec).resolve()
        print(f"{key}: копирую {source.name} ({source.stat().st_size / 1e9:.1f} ГБ) → {spec.path}")
        tmp = spec.path.with_suffix(".part")
        shutil.copyfile(source, tmp)
        tmp.replace(spec.path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=("tokenizer", "llama", "models"), help="выполнить только один шаг")
    parser.add_argument("--llama-variant", default="cuda-12.4", help="сборка llama.cpp для Windows (cuda-12.4, cpu, vulkan...)")
    args = parser.parse_args()

    if args.only in (None, "tokenizer"):
        prepare_tokenizer()
    if args.only in (None, "llama"):
        prepare_llama(args.llama_variant)
    if args.only in (None, "models"):
        prepare_models()
    print("Готово: сервису больше не нужен интернет.")


if __name__ == "__main__":
    main()
