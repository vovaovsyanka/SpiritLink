from .base import BaseClassifier
from .dictionary import Dictionary
from .lstm import LSTM
from .tfidf import TF_IDF
from .transformer import CategoryClassifier, MultilingualBert, RoSBERTa

# Классификаторы по уровню сложности
DIFFICULTY_CLASSIFIERS: dict[int, type[BaseClassifier]] = {
    1: Dictionary,
    2: TF_IDF,
    3: LSTM,
    4: MultilingualBert,
}

__all__ = [
    "BaseClassifier",
    "CategoryClassifier",
    "DIFFICULTY_CLASSIFIERS",
    "Dictionary",
    "LSTM",
    "MultilingualBert",
    "RoSBERTa",
    "TF_IDF",
]
