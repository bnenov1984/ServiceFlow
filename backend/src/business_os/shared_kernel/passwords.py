"""Credential primitives: argon2id hashing (portable per constraint C5) and
opaque session/CSRF tokens.

Lives in shared_kernel — not in `identity` — because both authentication planes
need it and neither may import the other: `identity` serves tenant users,
`platform_admin` serves Vendor Administrators, and the two are permanently
separate principals (ADR-BOS-009). These functions are genuinely neutral: they
know nothing about users, companies, tenancy or vendors, which is the bar
docs/business-os/04 sets for anything placed at this layer.

`identity.security` re-exports these names, so every existing call site
(`security.hash_secret(...)`) keeps working unchanged.
"""

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
