"""Базовые абстракции классификаторов."""

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Prediction:
    """
    label — решение классификатора (1 — вредоносный, 0 — безопасный);
    probability — вероятность класса 1, если модель её даёт; details — прочее для разбора ошибок.
    """

    label: int
    probability: Optional[float] = None
    details: dict = field(default_factory=dict)


class BaseClassifier(ABC):
    """
    Классификатор запросов: 1 — вредоносный, 0 — безопасный.

    Наследники реализуют _predict. predict() вызывает его под замком: быстрые токенизаторы HF
    и общая модель небезопасны при одновременных вызовах из нескольких потоков.
    """

    name: str = ""

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        obj._lock = threading.Lock()
        return obj

    @abstractmethod
    def _predict(self, text: str) -> Prediction:
        ...

    def predict(self, text: str) -> Prediction:
        with self._lock:
            return self._predict(text)

    def classify(self, text: str) -> int:
        return self.predict(text).label

    def get_name(self) -> str:
        return self.name or type(self).__name__
