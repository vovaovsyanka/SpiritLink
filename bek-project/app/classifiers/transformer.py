"""Общий классификатор опасный / безопасный на дообученной RoSBERTa."""

import logging
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app import settings
from app.text_utils import clean_for_bert

from .base import BaseClassifier, Prediction

logger = logging.getLogger(__name__)


def _resolve_device() -> torch.device:
    want = settings.BERT_DEVICE.lower()
    if want == "auto":
        want = "cuda" if torch.cuda.is_available() else "cpu"
    if want == "cuda" and not torch.cuda.is_available():
        logger.warning("BERT_DEVICE=cuda, но CUDA недоступна — BERT работает на процессоре")
        want = "cpu"
    device = torch.device(want)
    if device.type == "cuda":
        major, minor = torch.cuda.get_device_capability(0)
        logger.info("BERT на GPU: %s (sm_%d%d)", torch.cuda.get_device_name(0), major, minor)
        if f"sm_{major}{minor}" not in torch.cuda.get_arch_list():
            logger.warning(
                "Установленный PyTorch %s не содержит ядер для sm_%d%d — возможны ошибки CUDA. "
                "Установите сборку PyTorch под вашу видеокарту (для RTX 50xx — cu128).",
                torch.__version__, major, minor,
            )
    else:
        logger.info("BERT на процессоре")
    return device


class RoSBERTa(BaseClassifier):
    """Бинарный классификатор: argmax логитов, вероятность опасного — softmax. Только локальные файлы, без сети."""

    name = "RoSBERTa"

    def __init__(self, model_path: Path = settings.GENERAL_BERT_PATH):
        if not (model_path / "config.json").is_file() or not any(model_path.glob("*.safetensors")):
            raise FileNotFoundError(f"Нет весов BERT в {model_path}. Положите туда config.json и model.safetensors.")
        if not (model_path / "tokenizer.json").is_file() and not (model_path / "vocab.json").is_file():
            raise FileNotFoundError(
                f"Нет файлов токенайзера в {model_path}. Выполните при включённом интернете: python scripts/download_models.py"
            )
        self._device = _resolve_device()
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        # eager вместо sdpa: быстрые CUDA-ядра внимания падают на GPU,
        # которые установленный PyTorch не поддерживает (FATAL: kernel fmha_cutlass...)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            str(model_path), attn_implementation="eager", local_files_only=True
        )
        self._model.to(self._device).eval()

    def _predict(self, text: str) -> Prediction:
        inputs = self._tokenizer(
            clean_for_bert(text),
            truncation=True,
            max_length=settings.BERT_MAX_LENGTH,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
        return Prediction(label=int(probs.argmax().item()), probability=float(probs[1].item()))
