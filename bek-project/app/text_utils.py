"""Очистка текста: ввод игрока и подготовка для BERT."""

import re

_PUNCT_CHARS = (
    ".,!?;:()[]{}-_%$#@+=/\\*&~"
    "«»"        # « »
    "„“”"  # „ “ ”
    "‘’"        # ‘ ’
    "…"              # …
    "\"'"
)
_PUNCT = re.compile("[" + re.escape(_PUNCT_CHARS) + "]")
_SPACES = re.compile(r"\s+")
# Управляющие символы, кроме табуляции и переводов строки (NUL, например, PostgreSQL в тексте не принимает)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_for_bert(text: str) -> str:
    """Нижний регистр, удаление знаков препинания, схлопывание пробелов."""
    text = _PUNCT.sub(" ", str(text).strip().lower())
    return _SPACES.sub(" ", text).strip()


def clean_input(text: str) -> str:
    """Текст игрока без управляющих символов и одиночных суррогатов: безопасен для БД и моделей."""
    return _CONTROL.sub("", text.encode("utf-8", "ignore").decode("utf-8"))
