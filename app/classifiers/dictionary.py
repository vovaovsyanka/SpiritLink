"""Классификатор по словарю запрещённых слов."""

from app import settings

from .base import BaseClassifier


class Dictionary(BaseClassifier):
    name = "Dictionary"

    def __init__(self):
        raw = settings.BANNED_WORDS_PATH.read_text(encoding="utf-8")
        self.banned_words = [w.strip() for w in raw.split(", ") if w.strip()]

    def classify(self, text: str) -> int:
        return int(any(word in text for word in self.banned_words))
