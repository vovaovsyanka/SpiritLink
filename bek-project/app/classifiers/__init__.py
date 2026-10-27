from .base import BaseClassifier, Prediction

# RoSBERTa (transformer.py) импортируется там, где нужна: без неё сервис с STUB_MODELS=1 не требует torch.

__all__ = ["BaseClassifier", "Prediction"]
