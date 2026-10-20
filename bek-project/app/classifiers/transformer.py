"""Классификаторы на базе дообученных трансформеров."""

import logging
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app import settings
from app.text_utils import clean_for_bert

from .base import DEVICE, BaseClassifier

logger = logging.getLogger(__name__)


class TransformerClassifier(BaseClassifier):
    """Бинарный классификатор: argmax логитов дообученной модели."""

    def __init__(self, model_path: Path, tokenizer_name: str, name: str = ""):
        if name:
            self.name = name
        self._tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        # eager вместо sdpa: быстрые CUDA-ядра внимания падают на GPU,
        # которые установленный PyTorch не поддерживает (FATAL: kernel fmha_cutlass...)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            str(model_path), attn_implementation="eager"
        )
        self._model.to(DEVICE).eval()

    def _predict(self, text: str) -> int:
        inputs = self._tokenizer(
            clean_for_bert(text),
            truncation=True,
            max_length=settings.BERT_MAX_LENGTH,
            return_tensors="pt",
        )
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        with torch.no_grad():
            logits = self._model(**inputs).logits
        return int(logits.argmax(-1).item())


class RoSBERTa(TransformerClassifier):
    """Общий классификатор опасный / безопасный."""

    def __init__(self):
        super().__init__(settings.GENERAL_BERT_PATH, settings.GENERAL_BERT_TOKENIZER, "RoSBERTa")


class MultilingualBert(TransformerClassifier):
    def __init__(self):
        super().__init__(settings.E5_PATH, settings.E5_TOKENIZER, "MultilingualBert")


class CategoryClassifier(TransformerClassifier):
    """
    Определяет, принадлежит ли запрос целевой категории (1) или нет (0).
    Если модель категории не найдена, работает как заглушка: все запросы целевые.
    """

    def __init__(self, category: int):
        if category not in settings.CATEGORY_MODEL_PATHS:
            raise ValueError(
                f"Категория должна быть одной из {sorted(settings.CATEGORY_MODEL_PATHS)}. "
                f"Получена: {category}"
            )
        self.category = category
        self.name = f"CategoryBERT_{category}"

        model_path = settings.CATEGORY_MODEL_PATHS[category]
        self._stub = not model_path.exists()
        if self._stub:
            logger.warning(
                "Модель категории %s не найдена (%s) — используется заглушка", category, model_path
            )
        else:
            super().__init__(model_path, settings.CATEGORY_TOKENIZER)

    def _predict(self, text: str) -> int:
        return 1 if self._stub else super()._predict(text)
