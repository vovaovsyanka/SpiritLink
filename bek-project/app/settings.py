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

# ── Модели классификаторов ───────────────────────────────────────────────────
GENERAL_BERT_PATH = MODELS_DIR / "rosberta"
GENERAL_BERT_TOKENIZER = "ai-forever/ru-en-RoSBERTa"

LSTM_PATH = MODELS_DIR / "security_lstm_pytorch.pth"
TFIDF_PATH = MODELS_DIR / "tfidf_classifier.pkl"
BANNED_WORDS_PATH = MODELS_DIR / "banned_words.txt"

# Для каждой категории (3, 4, 5) — отдельная дообученная модель.
CATEGORY_MODEL_PATHS = {
    category: MODELS_DIR / f"ru-en-RoSBERTa_{category}" for category in (3, 4, 5)
}
CATEGORY_TOKENIZER = GENERAL_BERT_TOKENIZER

BERT_MAX_LENGTH = 256

# ── LLM (Ollama) ─────────────────────────────────────────────────────────────
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "https://ollama.com/api/generate")
LLM_MAX_TOKENS = 3000
LLM_TIMEOUT_SEC = 120
# Сколько запросов к Ollama может выполняться одновременно (остальные ждут в очереди)
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "16"))

# ── Заглушки для разработки (без весов моделей / без Ollama) ─────────────────
STUB_MODELS = os.getenv("STUB_MODELS", "0") == "1"
STUB_LLM = os.getenv("STUB_LLM", "0") == "1"

# ── База данных ──────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://spiritlink:spiritlink@localhost:5432/spiritlink"
)

# ── Аутентификация ───────────────────────────────────────────────────────────
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "30"))
# Через запятую; "*" — любой origin (токен передаётся в заголовке, cookie не используются)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# ── Лимиты попыток (каждая попытка в свободном промпте — платный вызов LLM) ──
ATTEMPTS_PER_HOUR = int(os.getenv("ATTEMPTS_PER_HOUR", "30"))
ATTEMPTS_PER_DAY = int(os.getenv("ATTEMPTS_PER_DAY", "200"))
MIN_SECONDS_BETWEEN_ATTEMPTS = float(os.getenv("MIN_SECONDS_BETWEEN_ATTEMPTS", "3"))
PROMPT_MAX_LENGTH = 2000

# ── Игра ─────────────────────────────────────────────────────────────────────
# Прохождение (уровень) → категория атак. Все уровни открыты сразу, порядок — только для вывода.
LEVEL_TO_CATEGORY: dict[str, int] = {
    "tony_stark": 3,
    "subnautica": 4,
    "cyberpunk": 5,
}
PASS_IDS: tuple[str, ...] = tuple(LEVEL_TO_CATEGORY)

# Уровень мира (выбирает игрок) → классификатор на третьем шаге каскада:
# 1 — словарь, 2 — TF-IDF, 3 — LSTM, 4 — RoSBERTa. Загружаются те, чьи файлы есть в models/.
WORLD_LEVELS: dict[int, str] = {
    1: "Словарь",
    2: "TF-IDF",
    3: "LSTM",
    4: "RoSBERTa",
}
DEFAULT_WORLD_LEVEL = 2
