"""Классификатор по словарю запрещённых слов."""

from app import settings

from .base import BaseClassifier, Prediction


class Dictionary(BaseClassifier):
    """Вероятности нет; для разбора ошибок отдаёт найденные запрещённые слова."""

    name = "Dictionary"

    def __init__(self):
        raw = settings.BANNED_WORDS_PATH.read_text(encoding="utf-8")
        self.banned_words = [w.strip() for w in raw.split(", ") if w.strip()]

    def _predict(self, text: str) -> Prediction:
        matched = [word for word in self.banned_words if word in text]
        return Prediction(label=int(bool(matched)), details={"matched": matched[:20]})
