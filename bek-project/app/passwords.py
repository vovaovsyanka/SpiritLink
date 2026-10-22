"""Выбор слова-якоря для прохождения игрока."""

import random

from app.ghosts import GHOSTS


def pick_secret(category: int, used: list[str]) -> tuple[str, list[str]]:
    """
    Случайное слово из пула призрака, которого не было в used.
    Когда пул исчерпан, used очищается (кроме последнего слова, чтобы не выдать его дважды подряд).
    Возвращает (слово, used после возможной очистки).
    """
    pool = GHOSTS[category]["passwords"]
    available = [word for word in pool if word not in used]
    if not available:
        used = used[-1:]
        available = [word for word in pool if word not in used] or pool
    return random.choice(available), used
