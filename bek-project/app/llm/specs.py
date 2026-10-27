"""Языковые модели (GGUF), которые использует пайплайн."""

from dataclasses import dataclass
from pathlib import Path

from app import settings


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repo: str                       # репозиторий Hugging Face с GGUF (нужен только scripts/download_models.py)
    size_gb: float                  # размер файла весов, ГБ
    quant: str = "Q4_K_M"           # подстрока в имени нужного файла репозитория
    slots: int = 2                  # параллельных запросов (слотов llama-server)
    ctx_per_slot: int = 3072        # контекст на один запрос
    extra_args: tuple = ()          # дополнительные аргументы llama-server

    @property
    def path(self) -> Path:
        return settings.LLM_DIR / f"{self.key}.gguf"


# Те же модели и параметры, что в experiments/config.py (по итогам экспериментов, experiments/REPORT.md).
MODELS: dict[str, ModelSpec] = {m.key: m for m in [
    ModelSpec("qwen3-4b", "Qwen/Qwen3-4B-GGUF", 2.5, slots=4),
    ModelSpec("qwen3.5-9b", "unsloth/Qwen3.5-9B-GGUF", 5.7),
    ModelSpec("yandexgpt5-lite-8b", "yandex/YandexGPT-5-Lite-8B-instruct-GGUF", 4.9),
    ModelSpec("gemma4-12b", "unsloth/gemma-4-12b-it-GGUF", 7.1),
]}


def required_models() -> list[str]:
    """Модель шлюза и мини-LLM, затем защитники по ступеням (без повторов, порядок запуска)."""
    keys = [settings.SERVICE_MODEL, *(model for model, _ in settings.FINAL_LADDER.values())]
    return list(dict.fromkeys(keys))
