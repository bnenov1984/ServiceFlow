"""Create the first Vendor Administrator. The only way one comes into existence.

Usage:
    uv run python -m business_os.platform_admin.bootstrap "Борис Ненов" boris@vendor.bg

The password is never a command-line argument (it would land in shell history
and in the process table). It is read, in order, from:

  1. the SERVICEFLOW_PLATFORM_ADMIN_PASSWORD environment variable — for an
     automated one-time provisioning step;
  2. an interactive no-echo prompt, asked twice and compared.

There is no default password, no unauthenticated HTTP bootstrap endpoint, and
no public registration route (ADR-BOS-009: vendor identities are created out of
band). Re-running the command with an existing email changes nothing — it does
not re-hash the password, rename the admin or reactivate a deactivated one — and
exits 0, so provisioning scripts stay idempotent.
"""

import getpass
import os
import sys

from business_os.platform_admin.service import create_platform_admin
from business_os.shared_kernel.db import open_session
from serviceflow.config import get_settings

# Windows consoles default to cp1252 — Cyrillic names crashed the final print
# after a successful seed (same fix as serviceflow.seed).
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

PASSWORD_ENV = "SERVICEFLOW_PLATFORM_ADMIN_PASSWORD"
MIN_PASSWORD_LENGTH = 12


def read_password() -> str:
    """Never echoes and never returns to the caller's stdout."""
    from_env = os.environ.get(PASSWORD_ENV)
    if from_env:
        password = from_env
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            raise SystemExit("passwords do not match")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    return password


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("SERVICEFLOW_DATABASE_URL is not set")

    name, email = sys.argv[1], sys.argv[2]
    password = read_password()

    for db in open_session(settings.database_url):
        admin, created = create_platform_admin(db, name, email, password)
        if created:
            print(f"OK: platform admin '{admin.name}' <{admin.email}> ({admin.id})")
        else:
            print(f"UNCHANGED: platform admin <{admin.email}> already exists ({admin.id})")


if __name__ == "__main__":
    main()
