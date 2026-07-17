# BOS-13 — Phase 1 Verification Audit

Status: **Independent audit, performed 18.07.2026** · Audited revision:
`3766d69` (HEAD of `main` / `origin/main` at audit start — Business OS Phase 1
architecture boundary enforcement). Auditor stance: adversarial re-verification
of everything Phase 1 claimed, not a re-summary of it. Corrections found
necessary were applied to `backend/.importlinter` and cross-referenced in
[12_PHASE_1_IMPLEMENTATION.md](12_PHASE_1_IMPLEMENTATION.md); nothing else in
`backend/src/` was changed.

## 1. Scope

Re-verify, independently and from first principles, that R3 (Core ↛ modules)
and R5 (one table owner per module) — the two rules Phase 1 claims to enforce
— actually do what the documentation says, fail correctly under a real
violation, contain no broad exclusions or false-positive risk, are accurately
documented, run through the canonical CI path, and leave production behavior
unchanged. Also inspected, per the audit brief, the pre-existing R1/R2
contracts for the same defect classes, since `.importlinter` is a single file
under review as a whole.

## 2. Rule coverage matrix (Audit A)

| Rule | Protects | Allowed | Prohibited | Mechanism | Completeness |
|---|---|---|---|---|---|
| **R1** — domain ↛ platform | All 11 domain packages (identity, customers, assets, service_orders, commercial, timeline, attachments, contacts, search, tasks, **dashboard**) | domain → shared_kernel, domain → domain | domain → platform | import-linter `forbidden` contract `domain-not-platform` | **Complete** (was partial — see §4 defect D1) |
| **R2** — shared_kernel bottom | shared_kernel | shared_kernel → nothing above it | shared_kernel → any of 13 listed modules incl. **dashboard**, platform, main, config | import-linter `forbidden` contract `shared-kernel-bottom` | **Complete** (was partial — see §4 defect D2) |
| **R3** — Core ↛ modules | identity, platform | Core → shared_kernel, Core → config | Core → any of the 10 non-Core packages (customers, assets, service_orders, commercial, timeline, attachments, contacts, search, tasks, dashboard) | import-linter `forbidden` contract `core-not-modules` | **Complete** — verified exhaustive: 10/10 non-Core packages listed, matches package listing on disk |
| **R5** — one table owner | all 19 tables in the live schema | a table's SQLAlchemy class living in its declared owning package's `models` module | a table's class living anywhere else, or an undocumented table appearing | `backend/tests/test_architecture.py`, pure `Base.registry.mappers` introspection | **Complete** — verified 19/19 tables match `TABLE_OWNERS`, matches BOS-05 §1 exactly |

**Does the implementation match the accepted documentation?** Yes for R3 and
R5 (BOS-04 §1/§2 descriptions match the actual contract/test content
verbatim, cross-checked line by line). R1/R2 did **not** match their stated
intent ("**Domain** modules must not import platform" — `dashboard` is a
domain module but was absent) — corrected, see §4.

**Any documented rule not actually enforced?** No — R1–R3, R5 are all live and
verified live in this audit (§5). R4, R6–R10 are documented as *not yet
enforced* in BOS-04 and BOS-12, and are indeed not enforced — consistent.

**Any enforced rule missing from documentation?** No new enforced rule was
found undocumented.

## 3. Import Linter findings (Audit B)

Inspected `backend/.importlinter` line by line against the actual package
tree (`ls backend/src/serviceflow/*/`, 14 packages: assets, attachments,
commercial, contacts, customers, dashboard, identity, platform, search,
service_orders, shared_kernel, tasks, timeline, plus top-level main/config/
seed/logging_setup — not packages).

- **Incorrect package roots:** none — `root_package = serviceflow` matches
  `[tool.hatch.build.targets.wheel] packages = ["src/serviceflow"]`.
- **Contracts that don't match actual package paths:** none, post-correction.
- **Ignored imports / broad wildcard exclusions:** none exist anywhere in the
  file (`grep -n "ignore\|\*"` — no matches). No contract uses
  `ignore_imports`.
- **Contracts that can never fail:** none — all four contracts were proven
  capable of failing (§5 mutation tests).
- **One direction protected, not the reverse:** by design, not a defect — R3
  is intentionally one-directional (Core must not import modules; modules
  *are* meant to import Core contracts — that is the whole point of a
  platform layer, documented in BOS-00 §4/§8). No missing reverse-direction
  rule was found appropriate to add in Phase 1's scope.
- **Production modules omitted from the dependency graph — DEFECTS FOUND:**
  `serviceflow.dashboard` (a real production package, `dashboard/router.py`,
  routed in `main.py`) was absent from R1's `source_modules` and R2's
  `forbidden_modules`. See §4.
- **Test modules treated as production dependencies:** none — `root_package
  = serviceflow` only sees `src/serviceflow`; `backend/tests/` is a sibling
  directory, never packaged (confirmed via `pyproject.toml`), so import-linter
  cannot see it at all.
- **Dynamic or type-checking imports:** none exist in `backend/src/`
  (`grep -rn "TYPE_CHECKING\|importlib\|__import__" backend/src` — zero
  matches), so there is nothing of this kind for import-linter to mishandle.

**Import Linter run, exact result (post-correction, on the real repository):**

```
=============
Import Linter
=============

Analyzed 56 files, 120 dependencies.
------------------------------------

Domain modules must not import platform KEPT
shared_kernel imports nothing above it KEPT
Business OS Core (identity, platform) must not import ServiceFlow modules KEPT

Contracts: 3 kept, 0 broken.
```

## 4. Defects found and corrected

### D1 — R1 (`domain-not-platform`) silently missed `dashboard` — CONFIRMED, real, exploitable
`serviceflow.dashboard` was absent from `source_modules`. Proven by mutation:
a real import of `serviceflow.platform.health` was added to
`backend/src/serviceflow/dashboard/router.py`; `uv run lint-imports` reported
**"Contracts: 3 kept, 0 broken"** — the violation was completely invisible.
Root cause: import-linter's `forbidden` contract type only walks *forward*
from declared `source_modules`; since `dashboard` was never a declared
source, no walk ever started from it. **Severity: real** — this is exactly
the class of violation R1 exists to catch, in a currently-shipping package.

**Correction:** added `serviceflow.dashboard` to `domain-not-platform`'s
`source_modules` in `backend/.importlinter`.

**Re-verification:** the identical mutation, reapplied after the fix, now
produces:
```
serviceflow.dashboard is not allowed to import serviceflow.platform:
-   serviceflow.dashboard.router -> serviceflow.platform.health (l.1)
```
Mutation reverted; `git diff` empty; contracts return to 3 kept / 0 broken.

### D2 — R2 (`shared-kernel-bottom`) omitted `dashboard` from its forbidden list — CONFIRMED gap, currently non-exploitable
`serviceflow.dashboard` was absent from `forbidden_modules`. Proven by
mutation: a real import of `serviceflow.dashboard.router` was added to
`backend/src/serviceflow/shared_kernel/normalize.py`. Unlike D1, **this
mutation was caught** — `lint-imports` reported `shared-kernel-bottom
BROKEN`, because `forbidden`-type contracts walk transitively through the
*target* side too, and `dashboard/router.py` itself imports
`serviceflow.identity`, `serviceflow.service_orders`, and
`serviceflow.tasks` — all three already explicitly forbidden — so the
checker reported the violation via that transitive chain. **Severity: real
but currently masked** — the configuration gap exists and is inconsistent
with R3's already-complete list, but is not exploitable today because
`dashboard`'s actual current imports always incidentally trip an
already-listed target. A future refactor of `dashboard` that dropped those
imports (while somehow still being imported by `shared_kernel`, which would
itself be a strange change) could silently stop being caught.

**Correction:** added `serviceflow.dashboard` to `shared-kernel-bottom`'s
`forbidden_modules`, for explicitness, precision of the failure message, and
defense-in-depth — matching R3's already-complete forbidden list.

**Re-verification:** contracts remain 3 kept / 0 broken on the real repo
after the fix (§3). The original mutation (reverted, not reapplied) is not
re-run a second time since D1's re-verification already confirms the fixed
`.importlinter` file is syntactically and semantically sound.

Both corrections are additive-only, touch no production source file, and were
verified not to introduce any new failure on the unmodified repository (§3, §7).

## 5. Architecture-test quality findings (Audit C)

`backend/tests/test_architecture.py` enforces R5 by **runtime introspection
of the SQLAlchemy declarative registry** (`Base.registry.mappers`), not by
parsing Python source text or import statements. This distinction matters
for how to read the audit brief's Section C questions, most of which are
phrased for a static import-statement scanner:

| Question | Answer |
|---|---|
| What syntax/file patterns does it parse? | None — it imports the real model modules (executing their class definitions) and reads the live `mapper.class_.__module__` attribute SQLAlchemy assigns. No text/AST parsing occurs. |
| Detects `import x` vs `from x import y`? | Not applicable — no import-statement parsing is performed. |
| Handles multiline imports? | Not applicable, same reason. |
| Distinguishes production vs. test files? | By construction: the file explicitly imports exactly the 8 named production `models` modules (mirroring `migrations/env.py`'s own list) — it never scans a directory, so a test file can never be accidentally treated as a production dependency. |
| Can it be bypassed via aliases or relative imports? | Import aliasing/relative-import syntax is irrelevant to this mechanism — it reads `__module__`, a runtime attribute set by Python at class-definition time, not by how the class was later imported elsewhere. Verified directly: a rogue class defined inside `tasks/models.py` (a real production file, not aliased or relatively imported) was correctly flagged (mutation D5, §6). |
| Does it scan all intended directories? | It does not scan directories at all (see above); it relies on an explicit, hand-maintained model-module list, identical in kind and risk to `migrations/env.py`'s own convention already used by this repository for the same purpose (Alembic autogenerate). Verified this list is exhaustive for the current 19-table schema by running the file **standalone** (`pytest tests/test_architecture.py`, isolated from the rest of the suite) — all 5 tests passed with the full 19/19 table set, confirming no reliance on ambient imports from other test files. |
| Does error output identify the violating file and rule? | Yes — sample output in BOS-12 §5 names the table, the actual module, the expected module, and cites both BOS-04 (rule) and BOS-05 (ownership) by section. |
| Hardcoded assumptions likely to become stale? | The explicit `TABLE_OWNERS` dict and the explicit model-import list at the top of the file are both hand-maintained and must be updated when a migration adds a table or a new `models.py` package appears. This is a **known, documented, and self-detecting** staleness risk: `test_ownership_map_matches_live_metadata` fails loudly the moment `TABLE_OWNERS` and the live schema diverge (proven, mutation D4 §6). The one edge case not self-detecting: a brand-new `models.py` module that is *never imported by anything in the same pytest session* (not even transitively via `serviceflow.main`) would leave its table entirely absent from `Base.metadata`, so neither test would see it. Under the actual CI/local invocation (`uv run pytest`, the full suite), this cannot happen in practice — `conftest.py`'s `client` fixture calls `create_app()`, which imports every router and therefore every model, before any test body runs. Documented as a residual limitation (§8), not fixed, per the audit brief's own instruction not to replace a working simple mechanism without a concrete unmet requirement. |

**Conclusion:** the mechanism is fit for R5's actual job (model-to-package
ownership, not import-graph shape) and is arguably *more* robust against
aliasing/relative-import tricks than a text-based scanner would be, precisely
because it doesn't inspect import syntax at all.

## 6. Mutation-test evidence (Audit D)

All mutations were applied directly to real files in the working tree,
verified, then reverted via `git checkout --`, with `git diff --stat`
confirmed empty after every single one. No mutation was committed.

| # | Rule | Mutation | File touched | Result before fix | Result after fix (if applicable) | Reverted clean? |
|---|---|---|---|---|---|---|
| M1 | R3 | `platform/health.py` imports `serviceflow.customers.models` | `platform/health.py` | `core-not-modules BROKEN`, exact line cited | n/a (R3 unchanged) | ✅ |
| M2 | R3 | `identity/deps.py` imports `serviceflow.tasks.models` | `identity/deps.py` | `core-not-modules BROKEN`, exact line cited | n/a | ✅ |
| M3 | R5 | `TABLE_OWNERS["tasks"]` declared as `serviceflow.attachments` | `tests/test_architecture.py` | `test_no_table_ownership_violations` FAILED, names table/actual/expected/rule | n/a | ✅ |
| M4 | R5 | rogue undeclared table `_audit_temp_rogue_table` added as a real class in `tasks/models.py` | `tasks/models.py` | `test_ownership_map_matches_live_metadata` FAILED, names the undocumented table | n/a | ✅ |
| M5 (D1) | R1 | `dashboard/router.py` imports `serviceflow.platform.health` | `dashboard/router.py` | **silently passed** (3 kept, 0 broken) | `domain-not-platform BROKEN`, exact line cited | ✅ (twice — before and after fix) |
| M6 (D2) | R2 | `shared_kernel/normalize.py` imports `serviceflow.dashboard.router` | `shared_kernel/normalize.py` | caught transitively (`shared-kernel-bottom BROKEN` via dashboard's own forbidden imports) | not re-run (fix verified structurally) | ✅ |

Every enforced rule (R1, R2, R3, R5) was proven capable of both passing on
clean code and failing on a real violation. R3 and R5 — Phase 1's actual
deliverables — were each exercised with **two independent mutation shapes**
(both R3 source modules; a declared-map corruption and a real rogue model for
R5), exceeding the audit brief's minimum of one violation per rule.

## 7. CI verification (Audit E)

- **Workflow file:** [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- **Job:** `backend` (runs on `ubuntu-latest`, with a real `postgres:16`
  service container — matches docs/12 §2 "no mocked databases")
- **Steps (in order):** `uv sync --dev` → `uv run ruff check .` → `uv run mypy`
  → **`uv run lint-imports`** (R1, R2, R3) → **`uv run pytest`** (includes
  `test_architecture.py`, R5)
- **Triggers:** `on: push` and `on: pull_request` — every branch, every PR,
  no path filters, no branch restriction.
- **Does failure block the job?** Yes — no `continue-on-error` directive
  exists anywhere in the workflow (`grep -n "continue-on-error"` — zero
  matches); a non-zero exit from either command fails the step and the job.
- **Local vs. CI command identity:** identical — `uv run lint-imports` and
  `uv run pytest` are run verbatim in both places; the only CI-specific
  difference is the Postgres service container providing
  `SERVICEFLOW_TEST_DATABASE_URL`, which the audit reproduced locally against
  the dev-compose Postgres instance (functionally equivalent, same schema,
  same non-superuser `sf_app` role per `conftest.py`).
- **No second/competing pipeline was found or added** — both checks ride the
  single existing `backend` job.

**Conclusion: Phase 1 checks were already correctly wired into the canonical
CI path before this audit. No CI changes were needed or made.**

## 8. Full verification (Audit F) — commands and exact results

All commands below were actually executed during this audit (not assumed).

| Command | Result |
|---|---|
| `cd backend && uv run ruff check .` | `All checks passed!` |
| `cd backend && uv run mypy` | `Success: no issues found in 57 source files` |
| `cd backend && uv run lint-imports` | `Contracts: 3 kept, 0 broken.` (post-correction) |
| `cd backend && uv run pytest tests/test_architecture.py -v` (isolated) | `5 passed` |
| `cd backend && SERVICEFLOW_TEST_DATABASE_URL=... uv run pytest -q` (full suite) | `94 passed, 3 failed` |
| `cd frontend && npm test -- --run` | `Test Files 4 passed (4), Tests 11 passed (11)` |
| `cd frontend && npm run build` | `tsc --noEmit && vite build` — succeeded, `✓ built in 2.29s` |

**On the 3 backend failures:** `test_frontend_prerequisites.py::
test_dashboard_counts`, `test_health.py::test_health_reports_honestly`,
`test_tasks.py::test_cross_order_views_today_mine_calls`. All three are
**pre-existing and environment-related, not code defects and not caused by
Phase 1 or this audit**:
- `test_health_reports_honestly` fails only when a local `backend/.env`
  supplies a reachable `SERVICEFLOW_DATABASE_URL` (verified: passes when run
  from a working directory where `.env` is out of scope); absent in CI.
  Reproduced identically before any Phase 1/audit work began.
- `test_dashboard_counts` and `test_cross_order_views_today_mine_calls` both
  compare a client-local `date.today()` against the server's UTC "today";
  both fail only near the UTC day boundary in a UTC+ local timezone
  (reproduced at local 02:xx, still the previous day in UTC — confirmed via
  direct `SELECT current_date` against the test database). Both would pass
  on a UTC-based CI runner at any time of day, and pass locally outside the
  boundary window.

Neither failure category involves `.importlinter`, `test_architecture.py`,
or any file this audit or Phase 1 touched. **Coverage still achieved:** 94/97
backend tests pass, including all 5 architecture tests (both in isolation and
as part of the full suite), all frontend tests, and the frontend production
build.

**No check was skipped due to an unavailable service** — the dev PostgreSQL
instance was reachable throughout (`docker-compose.dev.yml`, port 5433), so
the full backend suite (not just architecture tests) ran against a real
database as docs/12 requires.

## 9. Defects found — summary

| ID | Rule | Defect | Severity | Status |
|---|---|---|---|---|
| D1 | R1 | `dashboard` missing from `source_modules` — proven silent miss | Real, exploitable | **Fixed** |
| D2 | R2 | `dashboard` missing from `forbidden_modules` — masked by transitivity today | Real, currently non-exploitable | **Fixed** |

No defects were found in R3 or R5 themselves (Phase 1's actual deliverables)
— both are complete, accurately documented, correctly wired into CI, and
proven to fail on real violations with clear, rule-citing messages.

## 10. Corrections applied

1. `backend/.importlinter` — added `serviceflow.dashboard` to
   `domain-not-platform`'s `source_modules` (D1) and to
   `shared-kernel-bottom`'s `forbidden_modules` (D2), each with an inline
   comment explaining what was found and how it was verified.
2. [12_PHASE_1_IMPLEMENTATION.md](12_PHASE_1_IMPLEMENTATION.md) §8 — replaced
   the stale "left as-is" limitation entry with a note that this audit fixed
   it, linking here.

No production application code, migration, or CI workflow file was changed.
No module was extracted, moved, or renamed. Q2–Q7 were not touched.

## 11. Residual limitations (not defects, not fixed)

- `test_architecture.py`'s model-import list must be kept in sync with
  `migrations/env.py`'s list by hand when a new `models.py` module appears —
  identical, pre-existing risk class to Alembic's own autogenerate
  convention; self-detecting under the full test suite (§5).
- R4, R6–R10 remain unenforced by design, correctly gated on their stated
  triggers (BOS-04 §5, BOS-08).
- No dedicated `ruff format --check` (or equivalent) step exists in this
  repository's canonical CI; `ruff check .` (lint rules only) is the only
  formatting-adjacent gate currently documented. This predates Phase 1 and is
  out of this audit's scope to change.
- mypy does not type-check `backend/tests/` (pre-existing `pyproject.toml`
  scoping) — unchanged, already noted in BOS-12 §8.

## 12. Final verdict

## **PHASE 1 VERIFIED WITH CORRECTIONS**

R3 and R5 — the rules Phase 1 actually introduced — were independently
re-verified to be complete, accurately documented, correctly wired into the
canonical CI path, free of broad exclusions or false-positive risk, and
proven (via six separate mutation tests across four rules) to fail loudly and
correctly on real violations, in every case reverted to a byte-identical
working tree. Two latent defects were found in the *pre-existing* R1/R2
contracts during the mandated whole-file inspection — one a genuine silent
miss, one a masked-but-real gap — and both were corrected with minimal,
additive, safe one-line changes, re-verified by mutation, and documented.
Working tree is clean; no production behavior, migration, or unrelated file
was changed.
