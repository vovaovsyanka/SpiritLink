"""Хранилище текущих паролей по категориям."""

import random
from threading import Lock

from app.ghosts import GHOSTS


class PasswordStore:
    def __init__(self):
        self._passwords: dict[int, str] = {}
        self._lock = Lock()

    def current(self, category: int) -> str:
        """Текущий пароль категории; если его ещё нет — выбирается случайный."""
        with self._lock:
            if category not in self._passwords:
                self._passwords[category] = random.choice(GHOSTS[category]["passwords"])
            return self._passwords[category]

    def rotate(self, category: int) -> str:
        """Выбирает новый случайный пароль (после того, как старый угадан)."""
        with self._lock:
            self._passwords[category] = random.choice(GHOSTS[category]["passwords"])
            return self._passwords[category]
