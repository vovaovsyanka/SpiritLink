"""Пути, переменные окружения и игровые константы."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv необязателен
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static"
LOGS_DIR = BASE_DIR / "logs"

# ── Общий BERT (опасно / безопасно) ──────────────────────────────────────────
# В папке лежат и веса, и файлы токенайзера: сервис не ходит в Hugging Face (scripts/download_models.py).
GENERAL_BERT_PATH = MODELS_DIR / "rosberta"
BERT_MAX_LENGTH = 256
# cpu | cuda | auto. По умолчанию процессор: видеопамять нужна языковым моделям.
BERT_DEVICE = os.getenv("BERT_DEVICE", "cpu")

# ── LLM ──────────────────────────────────────────────────────────────────────
# Бэкенд генерации: llamacpp — свои процессы llama-server на этой машине (работает без интернета).
LLM_BACKEND = os.getenv("LLM_BACKEND", "llamacpp")
LLM_DIR = MODELS_DIR / "llm"                       # GGUF-файлы: <ключ модели>.gguf
TOOLS_DIR = BASE_DIR / "tools"                     # сюда ставится llama.cpp
LLAMA_SERVER_PATH = os.getenv("LLAMA_SERVER_PATH", "")
LLAMA_GPU_LAYERS = os.getenv("LLAMA_GPU_LAYERS", "")        # пусто — решает сам llama.cpp
LLAMA_SLOTS = int(os.getenv("LLAMA_SLOTS", "0"))             # 0 — по умолчанию для каждой модели (app/llm/specs.py)
LLAMA_EXTRA_ARGS = os.getenv("LLAMA_EXTRA_ARGS", "")         # дополнительные аргументы llama-server для всех моделей
LLAMA_START_TIMEOUT_SEC = int(os.getenv("LLAMA_START_TIMEOUT_SEC", "900"))
LLM_TIMEOUT_SEC = 120
# Сколько запросов может ждать свободного слота модели; дальше игрок получает 429 с Retry-After
LLM_MAX_QUEUE = int(os.getenv("LLM_MAX_QUEUE", "32"))

# Параметры генерации (как в экспериментах, experiments/config.py)
TEMPERATURE = 0.7
TOP_P = 0.9
CLASSIFIER_TEMPERATURE = 0.0       # шлюз категории отвечает детерминированно
MAX_NEW_TOKENS = {"defender": 160, "mini": 110, "classifier": 12}

# Модель шлюза категории и мини-LLM; защитники по ступеням (модель, вариант промпта).
# Выбор и обоснование: experiments/REPORT.md.
SERVICE_MODEL = "yandexgpt5-lite-8b"
FINAL_LADDER: dict[int, tuple[str, str]] = {
    1: ("qwen3-4b", "naive"),
    2: ("qwen3.5-9b", "naive"),
    3: ("qwen3.5-9b", "weak"),
    4: ("gemma4-12b", "weak"),
}

# ── Заглушки для разработки (без весов моделей / без LLM) ────────────────────
STUB_MODELS = os.getenv("STUB_MODELS", "0") == "1"   # вместо общего BERT — правила по ключевым словам
STUB_LLM = os.getenv("STUB_LLM", "0") == "1"         # вместо языковых моделей — заглушка

# ── База данных ──────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://spiritlink:spiritlink@localhost:5432/spiritlink"
)

# ── Аутентификация ───────────────────────────────────────────────────────────
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "30"))
# Через запятую; "*" — любой origin (токен передаётся в заголовке, cookie не используются)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# ── Лимиты попыток (каждая попытка в свободном промпте — работа языковой модели) ──
ATTEMPTS_PER_HOUR = int(os.getenv("ATTEMPTS_PER_HOUR", "30"))
ATTEMPTS_PER_DAY = int(os.getenv("ATTEMPTS_PER_DAY", "200"))
MIN_SECONDS_BETWEEN_ATTEMPTS = float(os.getenv("MIN_SECONDS_BETWEEN_ATTEMPTS", "3"))
PROMPT_MAX_LENGTH = 5000                      # защита от огромных тел запросов: больше — 422 от API
INPUT_MAX_CHARS = 800                         # больше (и до PROMPT_MAX_LENGTH) — призрак просит говорить короче, модели не вызываются
REPLY_CACHE_SIZE = int(os.getenv("REPLY_CACHE_SIZE", "2000"))   # повторы запросов отвечаются из кэша

# ── Игра ─────────────────────────────────────────────────────────────────────
# Прохождение (уровень) → категория атак. Все уровни открыты сразу, порядок — только для вывода.
LEVEL_TO_CATEGORY: dict[str, int] = {
    "tony_stark": 3,
    "subnautica": 4,
    "cyberpunk": 5,
}
PASS_IDS: tuple[str, ...] = tuple(LEVEL_TO_CATEGORY)

# Уровень мира (выбирает игрок) = ступень защитника из FINAL_LADDER.
WORLD_LEVELS: dict[int, str] = {
    1: "Простой",
    2: "Базовый",
    3: "Средний",
    4: "Сложный",
}
DEFAULT_WORLD_LEVEL = 2
