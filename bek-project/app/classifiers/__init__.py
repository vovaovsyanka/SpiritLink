from .base import BaseClassifier, Prediction
from .dictionary import Dictionary
from .lstm import LSTM
from .tfidf import TF_IDF
from .transformer import CategoryClassifier, RoSBERTa

# Классификаторы по уровню мира (сложности), ключи совпадают с settings.WORLD_LEVELS.
# Уровень 4 — тот же RoSBERTa, что и на первом шаге каскада (пайплайн переиспользует загруженную модель).
DIFFICULTY_CLASSIFIERS: dict[int, type[BaseClassifier]] = {
    1: Dictionary,
    2: TF_IDF,
    3: LSTM,
    4: RoSBERTa,
}

__all__ = [
    "BaseClassifier",
    "CategoryClassifier",
    "DIFFICULTY_CLASSIFIERS",
    "Dictionary",
    "LSTM",
    "Prediction",
    "RoSBERTa",
    "TF_IDF",
]
