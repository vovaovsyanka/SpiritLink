"""
Заглушка общего BERT для запуска без весов (STUB_MODELS=1). Только для разработки.

Решает по ключевым словам: «секрет», «слово», «пароль», «игнорир», «инструкц» — запрос опасный.
"""

from .base import BaseClassifier, Prediction

GENERAL_TRIGGERS = ("секрет", "слово", "пароль", "игнорир", "инструкц")


class StubGeneral(BaseClassifier):
    name = "Stub-RoSBERTa"

    def _predict(self, text: str) -> Prediction:
        matched = [word for word in GENERAL_TRIGGERS if word in text.lower()]
        return Prediction(
            label=int(bool(matched)), probability=0.9 if matched else 0.1, details={"stub": True, "matched": matched}
        )
