"""Базовые абстракции классификаторов."""

from abc import ABC, abstractmethod

import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class BaseClassifier(ABC):
    """Классификатор запросов: 1 — вредоносный, 0 — безопасный."""

    name: str = ""

    @abstractmethod
    def classify(self, text: str) -> int:
        ...

    def get_name(self) -> str:
        return self.name or type(self).__name__
