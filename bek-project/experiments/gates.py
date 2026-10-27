"""
BERT-шлюзы проекта: общий классификатор (опасно / безопасно) и категорийные (целевая категория / нет).
Веса берутся из models/ проекта (пути из app/settings.py). Модели грузятся по одной и выгружаются.
"""

import gc

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

import config  # noqa: F401  (добавляет корень проекта в sys.path)
from app import settings
from app.text_utils import clean_for_bert


def _probs(model_path, tokenizer_name: str, texts: list[str], batch_size: int = 16) -> np.ndarray:
    """Вероятность класса 1 («опасно» либо «целевая категория») для каждого текста."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path)).eval()
    try:
        model.to(device)
    except RuntimeError:  # не хватило видеопамяти — считаем на процессоре
        device = torch.device("cpu")
        model.to(device)
    out = []
    try:
        for i in range(0, len(texts), batch_size):
            batch = [clean_for_bert(t) for t in texts[i:i + batch_size]]
            enc = tokenizer(batch, truncation=True, max_length=settings.BERT_MAX_LENGTH, padding=True, return_tensors="pt")
            with torch.no_grad():
                logits = model(**{k: v.to(device) for k, v in enc.items()}).logits
            out.append(torch.softmax(logits.float(), dim=-1)[:, 1].cpu().numpy())
    finally:
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return np.concatenate(out)


def run_general(texts: list[str]) -> np.ndarray:
    return _probs(settings.GENERAL_BERT_PATH, settings.GENERAL_BERT_TOKENIZER, texts)


def run_category(ghost_id: int, texts: list[str]) -> np.ndarray:
    return _probs(settings.CATEGORY_MODEL_PATHS[ghost_id], settings.CATEGORY_TOKENIZER, texts)
