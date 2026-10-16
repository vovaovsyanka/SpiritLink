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

E5_PATH = MODELS_DIR / "multilingual-e5-small"
E5_TOKENIZER = "intfloat/multilingual-e5-small"

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

# ── Игра ─────────────────────────────────────────────────────────────────────
# Игровой уровень → категория классификатора
LEVEL_TO_CATEGORY: dict[str, int] = {
    "tony_stark": 3,
    "subnautica": 4,
    "cyberpunk": 5,
}

# Классификатор «сложности», применяемый в игре: 1 — словарь, 2 — TF-IDF, 3 — LSTM, 4 — E5-BERT
GAME_DIFFICULTY = 2
