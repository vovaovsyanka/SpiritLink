"""
Точка входа.

  uvicorn main:app --reload --host 0.0.0.0 --port 8000
  python main.py
"""

import logging
import os

import uvicorn

from app.api import app

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))
