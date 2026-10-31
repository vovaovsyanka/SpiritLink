"""
Лимиты попыток в свободном промпте: каждая попытка — платный вызов LLM.

- одновременно у игрока обрабатывается не больше одного запроса;
- между попытками не меньше MIN_SECONDS_BETWEEN_ATTEMPTS;
- не больше ATTEMPTS_PER_HOUR за час и ATTEMPTS_PER_DAY за сутки (считается по attempts).

Ввод слова-якоря лимитам не подчиняется (см. /predict), а в attempts попадают только запросы, дошедшие до классификатора:
отказы гигиены и сбои сервиса лимит не расходуют.

Отметка «запрос в обработке» хранится в памяти процесса. Пока сервер один (веса моделей
грузятся в процесс, воркер один), этого достаточно; при нескольких процессах — перенести в Redis.
"""

import math
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings
from app.models import Attempt

_busy_users: set[uuid.UUID] = set()


def _too_many(detail: str, retry_after: float) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail,
        headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
    )


@asynccontextmanager
async def user_request_slot(user_id: uuid.UUID):
    """Не даёт игроку отправить следующий запрос, пока не обработан предыдущий."""
    if user_id in _busy_users:
        raise _too_many("Предыдущий запрос ещё обрабатывается", 1)
    _busy_users.add(user_id)
    try:
        yield
    finally:
        _busy_users.discard(user_id)


async def check_attempt_limits(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Бросает 429 с Retry-After, если попытку сейчас делать нельзя."""
    hour, day = timedelta(hours=1), timedelta(days=1)
    in_last_hour = Attempt.created_at > func.now() - hour

    now, per_hour, oldest_in_hour, per_day, oldest_in_day, last = (await db.execute(
        select(
            func.now(),
            func.count().filter(in_last_hour),
            func.min(Attempt.created_at).filter(in_last_hour),
            func.count(),
            func.min(Attempt.created_at),
            func.max(Attempt.created_at),
        ).where(Attempt.user_id == user_id, Attempt.created_at > func.now() - day)
    )).one()

    if per_day >= settings.ATTEMPTS_PER_DAY:
        raise _too_many(
            f"Лимит попыток на сутки исчерпан ({settings.ATTEMPTS_PER_DAY})",
            (oldest_in_day + day - now).total_seconds(),
        )
    if per_hour >= settings.ATTEMPTS_PER_HOUR:
        raise _too_many(
            f"Лимит попыток на час исчерпан ({settings.ATTEMPTS_PER_HOUR})",
            (oldest_in_hour + hour - now).total_seconds(),
        )
    if last is not None:
        wait = settings.MIN_SECONDS_BETWEEN_ATTEMPTS - (now - last).total_seconds()
        if wait > 0:
            raise _too_many("Слишком часто, подождите немного", wait)
