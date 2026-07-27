"""Password/PIN hashing (argon2id, portable per constraint C5) and session tokens.

The implementations moved to `shared_kernel.passwords` when the Vendor Control
Plane arrived (ADR-BOS-009): `platform_admin` needs the same primitives but must
not import `identity` (protected boundary, docs/business-os/16). This module
stays as identity's own name for them — every existing `security.hash_secret(...)`
call site is unaffected.
"""

from business_os.shared_kernel.passwords import (
    hash_secret,
    hash_token,
    new_csrf_token,
    new_session_token,
    verify_secret,
)

__all__ = [
    "hash_secret",
    "hash_token",
    "new_csrf_token",
    "new_session_token",
    "verify_secret",
]
