# BOS-16 — Phase 3: Enforced Identity Public Boundary

Status: **Implemented, 18.07.2026** · Audited base revision: `25c3f9b` (main,
verified clean checkpoint — see Part A of this session). Scope:
[08_EVOLUTION_ROADMAP.md](08_EVOLUTION_ROADMAP.md) Phase 3 equivalent, brought
forward from its original "Deferred trigger" framing because Identity already
has concrete, current, non-hypothetical application-level reuse (8 routers) —
see [02_DOMAIN_CLASSIFICATION.md](02_DOMAIN_CLASSIFICATION.md) §3 ("Identity/
tenancy: Low extraction risk, already isolated").

**This is boundary hardening, not extraction.** Identity has not moved,
Business OS Core does not exist as a package, and no capability was promoted
into a generic platform SDK. What changed: the previously-documentation-only
"Core contract v1" (docs/business-os/14) is now mechanically enforced, one
real boundary violation was found and fixed, and one small gap in the public
contract's coverage (a company-profile accessor) was closed with a narrow,
already-needed addition.

## 1. Current Identity structure

```
backend/src/serviceflow/identity/
  __init__.py
  deps.py       — PUBLIC. FastAPI Depends()-wrapped, request-scoped.
  contracts.py  — PUBLIC (new this phase). Plain functions, not request-scoped.
  models.py     — INTERNAL. Company, User, AuthSession, AuditLog (SQLAlchemy).
  service.py    — INTERNAL. Session/auth business logic, seed_company, get_company, etc.
  security.py   — INTERNAL. Password/PIN hashing.
  router.py     — INTERNAL to the boundary rule, but composition-root-mounted (main.py).
```

## 2. Public contract

### 2.1 `identity.deps` (request-scoped, FastAPI `Depends()`)

| Export | Verified external consumers | In Phase 3 enforced contract? |
|---|---|---|
| `TenantDep` / `get_tenant` | All 8 external routers, 40+ handlers | Yes |
| `TenantDbDep` / `get_tenant_db` | Same 8 routers | Yes |
| `require_csrf` | 6 of 8 external routers (dashboard, search have no mutating endpoints) | Yes |
| `require_owner` | `customers/router.py` (1 real site) | Yes — narrow but real |
| `AuthDep` / `get_auth` | **None** — only `identity.router` itself | **No.** Per the instruction "do not preserve an export merely because it was documented in Phase 2," this is not promoted to the actively-relied-upon set. Kept available (a future handler needing raw session/user fields is a legitimate need), documented as unverified-externally. |

### 2.2 `identity.contracts` (plain functions, new this phase)

| Export | Purpose | Type returned |
|---|---|---|
| `get_company_profile(db, company_id) -> CompanyProfile` | The one real, current cross-module need found in discovery: `service_orders`' protocol-PDF endpoint needs company name + requisites (address/phone) for the document letterhead. Wraps `identity.service.get_company` (documented as the RLS-exempt Company lookup's "compensating control" — callers must not query `Company` directly). | `CompanyProfile` — a frozen dataclass (`name: str`, `requisites: dict[str, Any]`), never the `Company` ORM model. |

No other capability was added. `resolving the authenticated user` and
`authorization dependencies` were already fully covered by `deps.py`;
`checking organization context` is `TenantContext.company_id` (already
public) for scope, and `get_company_profile` for profile data. Nothing else
in the prompt's candidate list (session application entry points, etc.) had
a real current consumer, so nothing else was added — a broad Identity SDK
was deliberately not built.

### 2.3 A documented tension: `TenantDbDep` and "do not expose ORM sessions"

`TenantDbDep` resolves to a raw SQLAlchemy `Session`. The instructions for
this phase list "ORM sessions" among what the public contract must not
expose. **Reported, not silently resolved:** this codebase has no repository/
DAO layer anywhere, in any module — every module does its own
`scoped(select(...), Model, ctx)` queries directly against a `Session`
(`shared_kernel/db.py`, itself the documented tenant chokepoint). Removing
`TenantDbDep` from the contract, or wrapping it in something session-free,
would require introducing a repository abstraction across the entire
codebase — a real architectural change, explicitly out of this phase's scope
("boundary hardening, not extraction," "do not refactor unrelated code").
**Recommendation, per repository evidence:** keep `TenantDbDep` as specified;
treat "no ORM sessions" as the target state for a future module that ships
with a repository layer, not a Phase 3 blocker for the one that doesn't have
one yet. This is an **Open** item for a future phase, not resolved here.

## 3. Consumer matrix

Every import of `serviceflow.identity` from outside the `identity` package,
found via `grep -rn "from serviceflow\.identity" backend/`.

| Importing file | Imported symbol(s) | Source module | Purpose | Status (Phase 3 classification) | Action | Risk |
|---|---|---|---|---|---|---|
| `assets/router.py` | `TenantDbDep, TenantDep, require_csrf` | `identity.deps` | tenant scope + CSRF | ① public contract | none | — |
| `attachments/router.py` | `TenantDbDep, TenantDep, require_csrf` | `identity.deps` | same | ① public contract | none | — |
| `contacts/router.py` | `TenantDbDep, TenantDep, require_csrf` | `identity.deps` | same | ① public contract | none | — |
| `customers/router.py` | `TenantDbDep, TenantDep, require_csrf, require_owner` | `identity.deps` | same + owner gate | ① public contract | none | — |
| `dashboard/router.py` | `TenantDbDep, TenantDep` | `identity.deps` | tenant scope | ① public contract | none | — |
| `search/router.py` | `TenantDbDep, TenantDep` | `identity.deps` | same | ① public contract | none | — |
| `tasks/router.py` | `TenantDbDep, TenantDep, require_csrf` | `identity.deps` | same | ① public contract | none | — |
| `service_orders/router.py` | `TenantDbDep, TenantDep, require_csrf` | `identity.deps` | same | ① public contract | none | — |
| `service_orders/router.py` (before this phase) | `service` (module) → `.get_company(...)` | `identity.service` | company name/requisites for protocol PDF | ④ persistence-adjacent internal import (real violation) | **Migrated** to `identity.contracts.get_company_profile` | Low — single call site, narrow 2-field read, covered end-to-end by `test_protocol_pdf_renders_with_expected_content` |
| `seed.py` | `seed_company` | `identity.service` | composition-root dev/demo seeding | ⑥ composition root (documented exception, like `main.py`) | keep, explicit allowlist entry | none — not a module, not in `.importlinter` source scope |
| `main.py` | `router as auth_router`, `users_router` | `identity.router` | mounting the auth/users routes | ⑥ composition root | keep, explicit allowlist entry | none |
| `migrations/env.py` | `models as _identity_models` | `identity.models` | Alembic autogenerate metadata | ⑤/tooling exception — outside `root_package = serviceflow`'s tree entirely (`backend/migrations/`, not `backend/src/serviceflow/`) | none needed — already invisible to import-linter | none |
| 14 files under `backend/tests/` | `seed_company`, `service`, `security`, `models.User`, `models.AuthSession` | `identity.service`/`.security`/`.models` | tenant/user fixture bootstrap for that file's own test suite | ⑤ test-only exception — `backend/tests/` is a sibling directory, never part of `root_package = serviceflow`'s analyzed tree (confirmed, [13_PHASE_1_VERIFICATION_AUDIT.md](13_PHASE_1_VERIFICATION_AUDIT.md) §3) | none needed | none |

Classification key (per the six categories requested): ① documented public
contract · ② approved stable public module (same as ① here — deps/contracts
are the only two) · ③ Identity internal module · ④ persistence implementation
direct import · ⑤ test-only exception · ⑥ ambiguous/needs documentation
(resolved here as "composition root," a named, evidence-backed category, not
left ambiguous).

**Result: exactly one real violation found, and it is migrated. Zero
remaining production violations. No ratchet baseline/allowlist was needed** —
matching the Phase 1 pattern (docs/business-os/12 §3): check first, enforce
directly when clean.

## 4. Enforcement mechanism

### 4.1 Why `type = protected`, not `type = forbidden`

Phase 1's contracts (R1–R3) all use `forbidden`, which checks the full
*transitive* closure. A first attempt at this phase's contract using
`forbidden` (source = the 10 external modules, forbidden = identity's 4
internal submodules) **broke on every single router**, because every router
legitimately imports `identity.deps`, and `identity.deps` itself legitimately
imports `identity.service`/`.models` internally — `forbidden`'s transitive
walk correctly reports *reachability* but that is not what "using the public
API" means; it is expected and correct for the public module to have its own
internal dependencies.

Import-linter's `protected` contract type instead checks only **direct**
imports (`grimp.find_modules_that_directly_import`) — exactly the right
semantic: "may this module be imported directly by anything other than the
named allowed importers?" Discovered by reading
`importlinter/contracts/protected.py` directly (installed package source),
since this contract type is not otherwise referenced anywhere in this
repository's existing `.importlinter`.

### 4.2 The contract (`backend/.importlinter`)

```ini
[importlinter:contract:identity-public-boundary]
name = External modules must use identity's public contract only
type = protected
protected_modules =
    serviceflow.identity.models
    serviceflow.identity.service
    serviceflow.identity.security
    serviceflow.identity.router
allowed_importers =
    serviceflow.identity
    serviceflow.main
    serviceflow.seed
```

`allowed_importers = serviceflow.identity` (with `as_packages` defaulting to
`True`) expands to identity's own submodules — so `deps.py`, `contracts.py`,
and the four protected modules remain free to import each other internally.
`serviceflow.main` and `serviceflow.seed` are explicit, named,
narrow allowlist entries for the two composition-root files — not a
wildcard; each is one line, independently removable, matching how `main.py`
is already treated by the two Phase 1 contracts.

### 4.3 The re-export closure (`identity/deps.py`, `identity/contracts.py`)

Both public modules import identity's internal `service` module as `_service`
(leading underscore), not `service`. This closes the easy bypass
`from serviceflow.identity.deps import service` — which would otherwise work,
since `service` would be a plain attribute of an *allowed* module (`deps`),
and neither `forbidden` nor `protected` contracts track module *namespace*
contents, only import *statements*. See §6 for what this does and does not
close, verified by mutation testing.

## 5. Migrated consumers

One: `service_orders/router.py`. Before:

```python
from serviceflow.identity import service as identity_service
...
company = identity_service.get_company(db, tenant.company_id)
assert asset_type is not None and company is not None
```

After:

```python
from serviceflow.identity.contracts import get_company_profile
...
company = get_company_profile(db, tenant.company_id)
assert asset_type is not None
```

(`get_company_profile` asserts non-None internally and always returns a
`CompanyProfile`, so the caller's own None-check on `company` was removed —
the only behavior-preserving simplification directly enabled by the new
type, not a broader refactor.) Field access below (`company.name`,
`company.requisites`) is unchanged, since `CompanyProfile` carries the same
two field names.

## 6. Mutation-test evidence

All mutations applied to real files, verified, then reverted — `git diff
--stat` confirmed empty (or, for the one case that touched an already-edited
file, restored via the pre-mutation backup) after every one. Nothing
committed.

| # | What | Where | Expected | Result |
|---|---|---|---|---|
| M1 | `from serviceflow.identity.service import get_company` | `tasks/router.py` | `identity-public-boundary` BROKEN | ✅ BROKEN — `serviceflow.tasks.router -> serviceflow.identity.service (l.1)` |
| M2 | `from serviceflow.identity.models import User` | `dashboard/router.py` | BROKEN (persistence internals) | ✅ BROKEN — `serviceflow.dashboard.router -> serviceflow.identity.models (l.1)` |
| M3 | `from serviceflow.identity import service as totally_not_a_bypass` | `search/router.py` | BROKEN (aliasing doesn't help — edges are tracked by target module path, not local binding name) | ✅ BROKEN — same message as M1, alias name irrelevant |
| M4a | `from serviceflow.identity.deps import service` (pre-rename form) | Python REPL, against the real (post-rename) `deps.py` | Genuine `ImportError` — `deps` no longer has a `service` attribute | ✅ `ImportError: cannot import name 'service' from 'serviceflow.identity.deps' ... Did you mean: '_service'?` |
| M4b | `from serviceflow.identity.deps import _service` | Python REPL | **Residual gap, documented, not fixed** (see §7) | ⚠️ succeeds at the Python level; import-linter reports **4 kept, 0 broken** — this specific bypass is not mechanically caught |
| M5 | Re-add `service = _service` as a module-level name inside `deps.py` | `deps.py` (temporary) | The new `test_identity_public_modules_do_not_reexport_internal_service` pytest FAILS | ✅ FAILED with a message naming the offending module and the fix |

Approved-import-passes and zero-current-violations (item 1 of the required
proof set) is `Contracts: 4 kept, 0 broken` on the unmodified repository,
shown before and after every mutation above.

## 7. Behavioral verification

Full backend suite, before and after all Phase 3 changes:
`SERVICEFLOW_TEST_DATABASE_URL=... uv run pytest -q` → **98 passed** (97
pre-Phase-3 + 1 new architecture test), including `test_auth.py` (login, PIN
switch, CSRF, session expiry), `test_isolation.py` (cross-tenant RLS), and
`test_protocol.py::test_protocol_pdf_renders_with_expected_content` (the
exact endpoint whose company lookup was migrated — renders a real PDF and
inspects its text content). Zero test changes were made to any of these
files. `ruff check .`, `mypy`, and `uv run lint-imports` all pass.

## 8. Limitations

- **The underscore re-export path is not mechanically blocked** (M4b, §6).
  `from serviceflow.identity.deps import _service` still works. Closing it
  fully would require either AST-scanning every import statement for
  leading-underscore targets (a new, bespoke checker — the "large new
  framework" this phase is told to avoid, for a residual risk that requires
  someone to deliberately write code that imports a name Python's own error
  messages flag as private) or upgrading to a stricter contract mechanism.
  Documented, not fixed, per proportionality — the naming already makes a
  deliberate bypass attempt visibly wrong in review.
- **`TenantDbDep` exposes a raw `Session`** — see §2.3. Reported as a
  documented tension with the phase's abstract guidance, resolved in favor of
  repository evidence (no repository layer exists to route through instead).
- **`migrations/env.py` and `backend/tests/` are exempt from the boundary by
  construction** (never part of `root_package = serviceflow`'s analyzed
  tree), not by an explicit allowlist entry — consistent with how Phase 1's
  contracts already treat them (docs/business-os/13 §3).
- **`AuthDep` remains in `deps.py` but is not part of the actively-enforced
  "this is what external code should use" narrative** — it has no external
  consumer to protect or migrate. If one appears later, this document's §2.1
  table should be revisited.

## 9. Exit criteria (checked against the Phase 3 acceptance list)

1. Identity public API is explicit — `deps.py` (4 actively-used exports) +
   `contracts.py` (1 export), both documented in §2. ✅
2. External production consumers use approved entry points — confirmed for
   all 8 routers + the one migrated call site (§3, §5). ✅
3. Prohibited internal imports fail automatically — `identity-public-
   boundary` contract, proven by M1–M3 (§6). ✅
4. No database migration exists — none added; `git status` on
   `backend/migrations/` shows no changes. ✅
5. Authentication and authorization behavior unchanged — §7, 98/98 green,
   zero test file changes. ✅
6. Canonical tests pass — ruff, mypy, lint-imports, full pytest (§7). ✅
7. Architecture enforcement runs in CI — rides the existing `uv run lint-
   imports` step in `.github/workflows/ci.yml`; no new step needed (already
   established Phase 1 pattern). ✅
8. Every remaining exception is explicit and narrow — `serviceflow.main`,
   `serviceflow.seed` (2 named lines); the underscore-reexport and
   `TenantDbDep` items are documented limitations, not silent exceptions. ✅
9. Documentation matches actual enforcement — this document + updated cross-
   references (§10). ✅
10. No Phase 4 work started — commercial/module #2/extraction untouched. ✅

## 10. What this phase is not

Identity has **not** been extracted into a Business OS Core package. There is
no `business_os_core` package, no separate repository, no runtime plugin, no
module activation. `serviceflow.identity` is still exactly where it was —
this phase made its *existing* boundary explicit and mechanically checked,
nothing more. The distinction the roadmap draws (docs/business-os/08 Phase 3
"Core gets a name") remains a future, trigger-gated step, not something this
phase claims to have done.
