"""Хеширование паролей (argon2id) и токенов сессий (SHA-256)."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Параметры по умолчанию argon2-cffi: argon2id, 64 МиБ памяти, 3 прохода
_hasher = PasswordHasher()
# Для проверки при несуществующем логине: время ответа то же, что при неверном пароле
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> str:
    """Случайный токен для клиента (256 бит). В БД кладётся только hash_session_token(token)."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> bytes:
    # У случайного 256-битного токена перебор невозможен, медленный хеш не нужен
    return hashlib.sha256(token.encode()).digest()
