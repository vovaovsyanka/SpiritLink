"""TF-IDF + линейная модель."""

import pickle

from app import settings
from app.text_utils import clean_for_tfidf

from .base import BaseClassifier


class TF_IDF(BaseClassifier):
    name = "TF-IDF"

    def __init__(self):
        with open(settings.TFIDF_PATH, "rb") as f:
            data = pickle.load(f)
        self.clf = data["model"]
        self.vectorizer = data["vectorizer"]
        self.label_encoder = data["label_encoder"]

    def classify(self, text: str) -> int:
        features = self.vectorizer.transform([clean_for_tfidf(text)]).toarray()
        label = self.label_encoder.inverse_transform(self.clf.predict(features))[0]
        return 1 if str(label) == "unsafe" else 0
