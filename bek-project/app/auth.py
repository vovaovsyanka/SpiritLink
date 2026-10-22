"""Регистрация, вход, выход и зависимость current_user (Bearer-токен)."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings
from app.db import SessionLocal, get_db
from app.models import AuthSession, User, UserGameState
from app.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.security import (
    hash_password,
    hash_session_token,
    needs_rehash,
    new_session_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    login: str
    display_name: str
    role: str
    session_id: int


def _unauthorized(detail: str = "Требуется вход") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """
    Проверяет токен из заголовка Authorization. Своя короткая сессия БД: соединение не держится,
    пока обработчик ждёт LLM.
    """
    if credentials is None:
        raise _unauthorized()

    async with SessionLocal() as db:
        row = (await db.execute(
            select(AuthSession.id, User.id, User.login, User.display_name, User.role)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.session_token_hash == hash_session_token(credentials.credentials),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > func.now(),
                User.is_active.is_(True),
            )
        )).first()

    if row is None:
        raise _unauthorized("Сессия недействительна, войдите снова")
    session_id, user_id, login, display_name, role = row
    return CurrentUser(id=user_id, login=login, display_name=display_name, role=role, session_id=session_id)


def _open_session(db: AsyncSession, user_id: uuid.UUID, request: Request) -> TokenResponse:
    token = new_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_TTL_DAYS)
    db.add(AuthSession(
        user_id=user_id,
        session_token_hash=hash_session_token(token),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        expires_at=expires_at,
    ))
    return TokenResponse(token=token, expires_at=expires_at.isoformat().replace("+00:00", "Z"))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Создаёт аккаунт и сразу открывает сессию."""
    password_hash = await asyncio.to_thread(hash_password, data.password)
    user = User(
        login=data.login,
        password_hash=password_hash,
        display_name=data.display_name.strip() or data.login,
        last_login_at=func.now(),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Логин уже занят")

    db.add(UserGameState(user_id=user.id, world_level=settings.DEFAULT_WORLD_LEVEL))
    response = _open_session(db, user.id, request)
    await db.commit()
    return response


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await db.scalar(select(User).where(User.login == data.login))
    ok = await asyncio.to_thread(verify_password, user.password_hash if user else None, data.password)
    if not ok or user is None:
        raise _unauthorized("Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт заблокирован")

    if needs_rehash(user.password_hash):
        user.password_hash = await asyncio.to_thread(hash_password, data.password)
    user.last_login_at = func.now()
    response = _open_session(db, user.id, request)
    await db.commit()
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    """Закрывает текущую сессию (только это устройство)."""
    await db.execute(
        update(AuthSession).where(AuthSession.id == user.session_id).values(revoked_at=func.now())
    )
    await db.commit()
