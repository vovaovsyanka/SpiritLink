"""
Точка входа.

  python main.py
  uvicorn main:app --host 0.0.0.0 --port 8000

  Без --reload: при каждом перезапуске сервис заново загружает BERT и все языковые модели.
  Сервис работает без интернета (нужные файлы кладёт scripts/download_models.py).

  Чтобы запустить фронт:
  cd SpiritLinkAPP/builds/WebGL
  python -m http.server 8080
"""

import logging
import os

import uvicorn

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # сервис не ходит в Hugging Face
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

from app.api import app

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))
