"""Очистка текста для разных классификаторов."""

import re

_PUNCT_CHARS = (
    ".,!?;:()[]{}-_%$#@+=/\\*&~"
    "\u00ab\u00bb"        # « »
    "\u201e\u201c\u201d"  # „ “ ”
    "\u2018\u2019"        # ‘ ’
    "\u2026"              # …
    "\"'"
)
_PUNCT = re.compile("[" + re.escape(_PUNCT_CHARS) + "]")
_SPACES = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")
_NON_WORD = re.compile(r"[^\w\s]")


def clean_for_bert(text: str) -> str:
    """Нижний регистр, удаление знаков препинания, схлопывание пробелов."""
    text = _PUNCT.sub(" ", str(text).strip().lower())
    return _SPACES.sub(" ", text).strip()


def _strip_digits_and_punct(text: str) -> str:
    text = _DIGITS.sub("", text)
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Токенизация для LSTM (регистр сохраняется)."""
    return _strip_digits_and_punct(text).split()


def clean_for_tfidf(text: str) -> str:
    return _strip_digits_and_punct(text).lower()
