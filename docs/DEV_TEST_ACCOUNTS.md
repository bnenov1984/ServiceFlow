# Dev Test Accounts (development only)

Stable manual-QA identities — reuse these instead of creating a new tenant
for ordinary smoke testing.

## Vendor Console (`/vendor/login`)

- Email: `vendor@example.com`
- Password: `DevVendor123!`

## RepairFlow Tenant — "RepairFlow Demo Service" (`/login`)

- Owner: `owner@example.com` / `DevOwner123!` / PIN `1234`
- Worker: `worker@example.com` / `DevWorker123!` / PIN `4321`

`.local` addresses were tried first but are rejected by Pydantic's `EmailStr`
(`.local` is an IANA special-use/reserved TLD) — every login request 400s
before the password is ever checked. `example.com` (RFC 2606 reserved for
documentation/testing) passes `EmailStr` and is what's actually stored.

## Recreating them

If the dev database is ever reset, recreate the Vendor + Tenant + Owner with:

```bash
cd backend
SERVICEFLOW_PLATFORM_ADMIN_PASSWORD='DevVendor123!' \
  uv run python -m business_os.platform_admin.bootstrap "Dev Vendor Admin" vendor@example.com

uv run python -m serviceflow.seed "RepairFlow Demo Service" "Demo Owner" \
  owner@example.com DevOwner123! 1234
```

This seeds a **RepairFlow-only** tenant — the single-application shape the
Vendor Control Plane enforces for real companies (PO decision, 11.09.2026:
RepairFlow and PropertyFlow are mutually exclusive). Before 20.09.2026 the
script also activated `professional-services` unconditionally, so every dev,
staging and CI tenant was co-entitled in a way provisioning rejects.

For manual PropertyFlow work, or to reach the app chooser (`/choose-app`,
which IndexRoute only shows when both applications are active), opt in
explicitly:

```bash
uv run python -m serviceflow.seed "Dual Demo" "Demo Owner" \
  dual@example.com DevOwner123! 1234 --modules repairflow,professional-services
```

That company is **not representable in production** — treat it as a chooser
fixture, not a realistic tenant.

Both commands are idempotent — safe to rerun, and rerunning never changes an
existing account's password. Then add the Worker once via Settings →
Служители in the app (owner login), or `POST /api/v1/users`.

Automated tests (`pytest`, `vitest`) never use these accounts — every
DB-backed test creates and tears down its own throwaway tenant.
