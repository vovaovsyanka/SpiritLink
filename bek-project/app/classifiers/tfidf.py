"""TF-IDF + линейная модель."""

import pickle

from app import settings
from app.text_utils import clean_for_tfidf

from .base import BaseClassifier, Prediction


class TF_IDF(BaseClassifier):
    name = "TF-IDF"

    def __init__(self):
        with open(settings.TFIDF_PATH, "rb") as f:
            data = pickle.load(f)
        self.clf = data["model"]
        self.vectorizer = data["vectorizer"]
        self.label_encoder = data["label_encoder"]

        # Индекс класса "unsafe" в predict_proba; у моделей без вероятностей (например, LinearSVC) — None
        self._unsafe_index = None
        if hasattr(self.clf, "predict_proba"):
            classes = [str(c) for c in self.label_encoder.inverse_transform(self.clf.classes_)]
            if "unsafe" in classes:
                self._unsafe_index = classes.index("unsafe")

    def _predict(self, text: str) -> Prediction:
        features = self.vectorizer.transform([clean_for_tfidf(text)]).toarray()
        label = self.label_encoder.inverse_transform(self.clf.predict(features))[0]
        probability = None
        if self._unsafe_index is not None:
            probability = float(self.clf.predict_proba(features)[0][self._unsafe_index])
        return Prediction(label=1 if str(label) == "unsafe" else 0, probability=probability)
