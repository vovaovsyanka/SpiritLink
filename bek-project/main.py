"""
Точка входа.

  uvicorn main:app --reload --host 0.0.0.0 --port 8000
  python main.py
  
  Чтобы запустить фронт, зайти в папку Build и выполнить команду:
  python -m http.server 8080
"""

import logging
import os

import uvicorn

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

from app.api import app

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))
