"""Password/PIN hashing (argon2id, portable per constraint C5) and session tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()  # argon2id defaults


def hash_secret(secret: str) -> str:
    return _hasher.hash(secret)


def verify_secret(hashed: str, secret: str) -> bool:
    try:
        return _hasher.verify(hashed, secret)
    except VerifyMismatchError:
        return False


def new_session_token() -> tuple[str, str]:
    """Returns (raw_token_for_cookie, sha256_hash_for_storage)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)
