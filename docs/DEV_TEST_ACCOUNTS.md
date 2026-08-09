# Dev Test Accounts (development only)

Stable manual-QA identities — reuse these instead of creating a new tenant
for ordinary smoke testing.

## Vendor Console (`/vendor/login`)

- Email: `vendor@dev.local`
- Password: `DevVendor123!`

## RepairFlow Tenant — "RepairFlow Demo Service" (`/login`)

- Owner: `owner@dev.local` / `DevOwner123!` / PIN `1234`
- Worker: `worker@dev.local` / `DevWorker123!` / PIN `4321`

## Recreating them

If the dev database is ever reset, recreate the Vendor + Tenant + Owner with:

```bash
cd backend
SERVICEFLOW_PLATFORM_ADMIN_PASSWORD='DevVendor123!' \
  uv run python -m business_os.platform_admin.bootstrap "Dev Vendor Admin" vendor@dev.local

uv run python -m serviceflow.seed "RepairFlow Demo Service" "Demo Owner" \
  owner@dev.local DevOwner123! 1234
```

Both commands are idempotent — safe to rerun, and rerunning never changes an
existing account's password. Then add the Worker once via Settings →
Служители in the app (owner login), or `POST /api/v1/users`.

Automated tests (`pytest`, `vitest`) never use these accounts — every
DB-backed test creates and tears down its own throwaway tenant.
