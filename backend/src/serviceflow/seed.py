"""Dev/staging seed: company + Owner user (self-serve registration arrives in Етап 3).

Usage:
    uv run python -m serviceflow.seed "Сервиз Демо" "Мария" maria@demo.bg парола123 [PIN]
"""

import sys

# Registers the company_provisioned -> seed_default_types subscriber (import-
# time side effect, business_os.shared_kernel.events.subscribe). Without this
# import, seed_company()'s publish() below reaches zero subscribers when run
# standalone (this script never imports serviceflow.main), leaving the new
# company with no default RepairFlow asset types.
import serviceflow.assets.service  # noqa: F401,E402
from business_os.identity.service import activate_module, seed_company
from business_os.shared_kernel.db import open_session
from serviceflow.config import get_settings

# Windows consoles default to cp1252 — Cyrillic company names crashed the final
# print after a successful seed. Force UTF-8 for our own output.
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def main() -> None:
    if len(sys.argv) < 5:
        print(__doc__)
        raise SystemExit(2)
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("SERVICEFLOW_DATABASE_URL is not set")
    company_name, owner_name, email, password = sys.argv[1:5]
    pin = sys.argv[5] if len(sys.argv) > 5 else None
    for db in open_session(settings.database_url):
        company = seed_company(db, company_name, owner_name, email, password, pin)
        activate_module(db, company.id, "professional-services")
        print(f"OK: company '{company.name}' ({company.id})")


if __name__ == "__main__":
    main()
