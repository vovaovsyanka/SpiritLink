"""Базовые абстракции классификаторов."""

import logging
import threading
from abc import ABC, abstractmethod

import torch

logger = logging.getLogger(__name__)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _log_device() -> None:
    if DEVICE.type != "cuda":
        logger.info("Инференс на CPU")
        return
    major, minor = torch.cuda.get_device_capability(0)
    logger.info("Инференс на GPU: %s (sm_%d%d)", torch.cuda.get_device_name(0), major, minor)
    if f"sm_{major}{minor}" not in torch.cuda.get_arch_list():
        logger.warning(
            "Установленный PyTorch %s не содержит ядер для sm_%d%d — возможны ошибки CUDA. "
            "Установите сборку PyTorch под вашу видеокарту (для RTX 50xx — cu128).",
            torch.__version__, major, minor,
        )


_log_device()


class BaseClassifier(ABC):
    """
    Классификатор запросов: 1 — вредоносный, 0 — безопасный.

    Наследники реализуют _predict. classify() вызывает его под замком: быстрые токенизаторы HF
    и общая модель на GPU небезопасны при одновременных вызовах из нескольких потоков,
    а на одном GPU параллельный инференс всё равно выполняется последовательно.
    """

    name: str = ""

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        obj._lock = threading.Lock()
        return obj

    @abstractmethod
    def _predict(self, text: str) -> int:
        ...

    def classify(self, text: str) -> int:
        with self._lock:
            return self._predict(text)

    def get_name(self) -> str:
        return self.name or type(self).__name__
