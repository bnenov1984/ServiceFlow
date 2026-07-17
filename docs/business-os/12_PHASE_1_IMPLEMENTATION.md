# BOS-12 — Phase 1 Implementation: Architecture Boundary Enforcement

Status: **Implemented, 18.07.2026** · Scope: [08_EVOLUTION_ROADMAP.md](08_EVOLUTION_ROADMAP.md)
Phase 1 only. Authoritative baseline confirmed by the PO for this phase:
web-first SaaS ([docs/14](../14_WEB_FIRST_PIVOT.md)); the local edition is
deferred and did not drive any decision below.

## 1. What this phase enforces

Two rules from [04_DEPENDENCY_RULES.md](04_DEPENDENCY_RULES.md) §2, both
already true of the codebase — this phase makes them fail loudly if a future
change breaks them. Nothing else from 04 (R4, R6–R10) is enforced yet; they
require artifacts (contracts.py files, a second module) that do not exist.

| Rule | What it forbids | Mechanism | Where |
|---|---|---|---|
| **R3** | Business OS Core (`identity`, `platform`) importing any vertical or shared module (`customers`, `assets`, `service_orders`, `commercial`, `timeline`, `attachments`, `contacts`, `search`, `tasks`, `dashboard`) | new import-linter contract `core-not-modules` | [backend/.importlinter](../../backend/.importlinter) |
| **R5** | A table's SQLAlchemy mapped class living outside its declared owning package's `models` module | new pytest module, pure metadata introspection | [backend/tests/test_architecture.py](../../backend/tests/test_architecture.py) |

## 2. Tool selection

**Inspected first:** the repo already runs `ruff` (style/correctness),
`mypy --strict` (types), `import-linter` (module boundaries — two contracts
already live in `backend/.importlinter`, wired into CI as `uv run
lint-imports`), and `pytest` (integration + a few pure-unit tests).

**R3 (Core ↛ modules):** import-linter already does exactly this job for the
two existing contracts (R1: domain ↛ platform; R2: shared_kernel bottom). R3
is the same shape of rule (a `forbidden` contract between named packages), so
it is one more stanza in the same file — no new tool, no new dependency, no
second lint pipeline. Rejected alternatives: a custom AST-walking script
(reinvents what import-linter already does correctly); `flake8-tidy-imports`
or similar (adds a dependency for a subset of what's already installed).

**R5 (one owner per table):** no existing tool in the repo checks this — it
is repository-specific (which *package* a SQLAlchemy model lives in, not an
import-graph fact import-linter can express). A ~130-line pytest module using
`Base.registry.mappers` (already how `migrations/env.py` collects metadata)
is the smallest mechanism that expresses it, runs in the existing `pytest`
invocation, needs no database connection, and takes <0.2s. Rejected
alternatives: a dedicated architecture-testing library (e.g. `pytest-archon`,
`import-linter`'s own `layers` contract type stretched to fit) — none of them
naturally express "this table's class lives in this package" without more
configuration than the direct pytest check; adding one would be exactly the
"large dependency where a small repository-specific test is sufficient" this
phase is told to avoid.

## 3. Ratchet status: no baseline needed

Both rules were checked against the current repository **before** being
enforced (docs/business-os/11_ARCHITECTURE_REVIEW.md §2 already established
this for R3; re-verified for this phase):

- **R3:** `identity/` imports only `serviceflow.config` and
  `serviceflow.shared_kernel.*`; `platform/health.py` imports only
  `serviceflow.config`. Zero existing imports of any vertical/shared module.
  Verified by temporarily inserting `from serviceflow.customers.models import
  Customer` into `platform/health.py` and confirming `uv run lint-imports`
  reports the new contract `BROKEN` with a precise message; the file was then
  restored and diffed byte-for-byte identical to its original.
- **R5:** all 19 tables' mapped classes already live in their declared owning
  package (`Base.registry.mappers` introspection matches
  [05_DATA_OWNERSHIP.md](05_DATA_OWNERSHIP.md) §1 exactly — including
  `document_sequences`, whose *ownership* is documented Open for Етап 4 but
  whose *current code location* is unambiguous). Verified by temporarily
  mis-declaring `customers` as owned by `serviceflow.assets` in the test's own
  ownership map and confirming `test_no_table_ownership_violations` fails with
  a message naming the table, the actual vs. expected module, and the two
  governing documents; the file was then restored and diffed byte-for-byte
  identical to its original.

**Conclusion: enforce directly, no allowlist/baseline file.** Per the
roadmap's ratchet requirement, a baseline is only created when violations
already exist; none do. If a future audit finds one (e.g. after a rebase or a
branch merge), add a narrow, named, individually-removable entry at that time
— do not retrofit one speculatively now.

## 4. How to run the checks

**Locally**, from `backend/`:

```
uv run lint-imports      # R3 (+ existing R1, R2)
uv run pytest tests/test_architecture.py -v   # R5
uv run pytest            # R5 runs as part of the full suite too
```

**In CI:** both ride the existing canonical jobs in
[.github/workflows/ci.yml](../../.github/workflows/ci.yml) — `lint-imports`
was already a CI step (now checks one more contract); `test_architecture.py`
runs automatically as part of the existing `uv run pytest` step (it is a file
under `backend/tests/`, the configured `testpaths`). No new CI job, no new
workflow file.

## 5. Failure messages

**R3** (import-linter's own format, includes the exact violating import line):

```
Business OS Core (identity, platform) must not import ServiceFlow modules
-------------------------------------------------------------------------
serviceflow.platform is not allowed to import serviceflow.customers:
-   serviceflow.platform.health -> serviceflow.customers.models (l.1)
```

**R5** (pytest assertion, names the table, actual vs. expected module, and
cites both governing documents):

```
Table ownership violations found:
'customers': mapped by 'serviceflow.customers.models', expected
'serviceflow.assets.models' (rule R5 — docs/business-os/04_DEPENDENCY_RULES.md;
ownership — docs/business-os/05_DATA_OWNERSHIP.md §1)
```

## 6. How to add a new rule (for the next contributor)

- **A new "package X must not import package Y" rule:** add a
  `[importlinter:contract:...]` stanza to `backend/.importlinter` following
  the existing three; give it a comment citing the BOS-04 rule number and
  rationale, same as R1–R3 above.
- **A new "table X must be owned by package Y" fact:** add one entry to
  `TABLE_OWNERS` in `backend/tests/test_architecture.py`, and the matching row
  in [05_DATA_OWNERSHIP.md](05_DATA_OWNERSHIP.md) §1, in the same PR
  (ADR-BOS-003). `test_ownership_map_matches_live_metadata` will fail loudly
  if a migration adds a table and this step is forgotten.
- **Rules not yet mechanizable** (R4 contracts-only-at-context-edges, R6–R10):
  do not force them now — they need artifacts (`contracts.py` files, a real
  second module) that this phase deliberately does not create. See
  [04_DEPENDENCY_RULES.md](04_DEPENDENCY_RULES.md) §5 for their trigger
  points.

## 7. How to remove a baseline entry

Not applicable this phase — no baseline exists (§3). If one is added later,
its own entry must state the removal condition (e.g. "remove when module X is
refactored to use the Y contract"); removing it is deleting that one line from
the allowlist and re-running the check.

## 8. Limitations of this implementation

- **R1 (`domain-not-platform`) does not list `serviceflow.dashboard`** in its
  `source_modules`, even though `dashboard` is a domain package like the
  others. This is a **pre-existing gap in a contract this phase did not
  touch** (found during R3 review evidence-gathering, not introduced here) —
  left as-is per this phase's explicit "avoid unrelated technical debt"
  scope. In practice `dashboard/router.py` does not import `platform`, so
  there is no live violation; the gap is a coverage hole, not an active
  breach. Recommend closing it as a one-line addition whenever `.importlinter`
  is next touched for an unrelated reason.
- **R5 covers table ownership only**, not read/write access patterns within a
  context (rule R6/R7 territory) — a package inside Service Operations
  reading another Service Operations package's model is still invisible to
  this check, by design (BOS-04 R6 permits it).
- **No enforcement exists yet for R4** (contracts-only at context edges) —
  correctly deferred until `commercial/` has real code (Етап 4, roadmap
  Phase 4).
- **mypy does not type-check `backend/tests/`** (`pyproject.toml`
  `[tool.mypy] packages = ["serviceflow"]` scopes it to `src/serviceflow`
  only) — pre-existing repository convention, unchanged by this phase;
  `test_architecture.py` is covered by `ruff` and by running under `pytest`.

## 9. Frozen vs. future-candidate rules (for readers of 04)

**Enforced now (this phase):** R1, R2 (pre-existing), R3, R5 (baseline
check only — see §8).

**Documented but not yet enforced (future phases, per
[08_EVOLUTION_ROADMAP.md](08_EVOLUTION_ROADMAP.md)):** R4, R6 (a
non-rule — explicitly permits same-context sharing), R7 (rides R4's
mechanism), R8 (trigger-scheduled, not phase-scheduled — see BOS-11 F4), R9
(frontend ESLint zones — Phase 2), R10 (review convention, not automatable
without more evidence of need).
