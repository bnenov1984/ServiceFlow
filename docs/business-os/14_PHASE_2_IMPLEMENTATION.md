# BOS-14 — Phase 2 Implementation: Additive Guard Rails

Status: **Implemented, 18.07.2026** · Scope: [08_EVOLUTION_ROADMAP.md](08_EVOLUTION_ROADMAP.md)
Phase 2 only, as revised by [11_ARCHITECTURE_REVIEW.md](11_ARCHITECTURE_REVIEW.md)
F4/F5. Two items: a frontend boundary check, and Core-contract-v1 docstrings.
No new packages, no module extraction, no production behavior change.

## 1. What this phase enforces

| Item | What it protects | Mechanism | Where |
|---|---|---|---|
| **R9 (revised)** | `frontend/src/{lib,components,i18n,generated}` never import from a feature folder (`auth`, `customers`, `dashboard`, `intake`, `order`, `orders`, `shell`) | new `vitest` test file, Vite-native file enumeration | [frontend/src/architecture.test.ts](../../frontend/src/architecture.test.ts) |
| **Core contract v1** | Documents `identity/deps.py`'s public surface as the intended Core dependency contract | module docstring only | [backend/src/serviceflow/identity/deps.py](../../backend/src/serviceflow/identity/deps.py) |

## 2. Why R9 was revised, not implemented as originally written

[04_DEPENDENCY_RULES.md](04_DEPENDENCY_RULES.md) originally stated R9 as:
*"Frontend feature folders may import `lib/`, `components/`, `i18n/`,
`generated/` — never each other's internals."* Before enforcing it, the same
ratchet check Phase 1 applied to R3/R5 was applied here — and it failed:

```
customers/CustomerAssetsSection.tsx  -> ../intake/AssetTypeIcon
customers/CustomerOrdersSection.tsx  -> ../orders/types
customers/CustomerProfilePage.tsx    -> ../auth/AuthContext
customers/CustomerProfilePage.tsx    -> ../order/ContactsSection
order/AssetCard.tsx                  -> ../intake/AssetTypeIcon
order/OrderHeader.tsx                -> ../auth/AuthContext
orders/OrdersPage.tsx                -> ../order/dialogs/ApprovalDialog
orders/OrderStatusActions.tsx        -> ../order/dialogs/{Approval,Delivery,Reason}Dialog
shell/AppShell.tsx                   -> ../auth/{PinSwitchDialog,AuthContext}
```

Nine real, working imports across five feature folders — all legitimate
reuse (a shared icon component, a shared auth context, shared dialogs) inside
a single-vertical SPA with no second module's frontend to protect against yet
(docs/business-os/09 Q7, still Open). Enforcing the literal rule now would
have meant either breaking the build or writing an allowlist covering most of
the app's real cross-feature relationships — which is not a guard rail, it is
theater. Per [12_PHASE_1_IMPLEMENTATION.md](12_PHASE_1_IMPLEMENTATION.md)'s
ratchet requirement ("only enforce what already holds"), this was not forced.

**What does hold, verified with zero exceptions:** `lib/`, `components/`,
`i18n/`, `generated/` never import from any of the seven feature folders.
This is the frontend's real analogue to the backend's R2 (shared_kernel is
the bottom layer) — the boundary that matters for a future module's UI being
able to reuse the shared layer without inheriting ServiceFlow-specific
coupling. This is what Phase 2 implements.

R9-as-originally-conceived (true feature-to-feature isolation) remains a
documented future candidate, deferred to roadmap Phase 5 (second module),
where it will have something real to protect.

## 3. Tool selection

**Inspected first:** `frontend/package.json` has no `lint` script, no ESLint
in `devDependencies`, and no ESLint config file exists anywhere in the repo
(`eslint.config.js`, `.eslintrc*` — none found). `.github/workflows/ci.yml`'s
`frontend` job runs only `npm ci`, `npm test`, `npm run build` — no lint step.
The roadmap's original phrasing ("ESLint zones... small config") assumed
ESLint already existed, as it typically would mirror the backend's existing
import-linter; it does not.

**Decision:** do not install ESLint for this one check. Installing a full
lint framework (eslint, `@typescript-eslint/*`, `eslint-plugin-import`, a new
flat config, a new `lint` script, a new CI step) to enforce a single boundary
rule is disproportionate — the same "avoid a large dependency where a small
repository-specific test suffices" principle Phase 1 applied to R5 on the
backend. Instead: a `vitest` test file, since `vitest` is already installed,
already wired into CI (`npm test`), and Vite's built-in `import.meta.glob`
(typed via the already-present `vite/client` types) can enumerate and read
source files without any new dependency at all.

**Rejected alternative:** using Node's `fs`/`path`/`url` to walk the
filesystem (the backend's own idiom, and this file's first draft). Reverted
after `tsc --noEmit` (part of `npm run build`) failed — this repo has no
`@types/node`, and `tsconfig.json`'s `"types": ["vite/client"]` deliberately
excludes Node globals. Adding `@types/node` purely for one test file was
judged not worth a new devDependency when `import.meta.glob` does the same
job with zero additions.

## 4. Ratchet status: no baseline needed (for the rule actually implemented)

The *implemented* rule (leaf dirs ↛ feature folders) was checked before
enforcement and found to hold with zero violations
(`lib/components/i18n/generated` — none import from any feature folder).
Enforced directly, no allowlist. The *original* R9 wording was not
implemented at all (§2) rather than baselined — a baseline covering 9 of what
would likely be dozens of legitimate future cross-imports would not have
been "narrow," failing the roadmap's own ratchet-requirement bar for when a
baseline is appropriate.

## 5. Mutation-test evidence

All mutations applied to real files, verified, then reverted via
`git checkout --`, confirmed byte-identical (`git diff --stat` empty) after
every one. Nothing committed.

| Mutation | File | Result before revert |
|---|---|---|
| `lib/api.ts` imports `../auth/AuthContext` | `frontend/src/lib/api.ts` | `architecture.test.ts` FAILED — reported the exact file and the matched import text |
| new undeclared top-level folder `_audit_temp_dir` under `src/` | `frontend/src/` | the completeness test FAILED — reported the drift between the declared lists and the real folder listing |

Both reverted; `npm test -- --run` returns to 16/16 passing (11 pre-existing
+ 5 new) and `npm run build` succeeds afterward.

## 6. How to run the check

**Locally**, from `frontend/`:
```
npx vitest run src/architecture.test.ts   # this check alone
npm test                                   # full suite, includes it
npm run build                              # also exercises it via tsc
```

**In CI:** rides the existing `frontend` job's `npm test` step in
[.github/workflows/ci.yml](../../.github/workflows/ci.yml) — no new step, no
new job, no new pipeline.

## 7. Failure message sample

Actual output from the mutation test in §5 (`lib/api.ts` temporarily made to
import `../auth/AuthContext`):

```
lib\api.ts: imports from "auth" (from "../auth/)
```

One line per violating file, naming the file, the feature folder it
incorrectly reached into, and the matched import text.

## 8. Core contract v1 (identity/deps.py)

Added a docstring to `backend/src/serviceflow/identity/deps.py` naming its
five exports (`TenantDep`/`get_tenant`, `TenantDbDep`/`get_tenant_db`,
`AuthDep`/`get_auth`, `require_csrf`, `require_owner`) as the intended public
Core contract, and stating explicitly that everything else in `identity`
(models, service, security, router) is implementation detail. Documentation
only — no new package, no code behavior change (verified: full backend test
suite unaffected, `ruff`/`mypy`/`lint-imports` all pass unchanged).

## 9. Limitations

- The frontend check relies on a hand-maintained `LEAF_DIRS`/`FEATURE_FOLDERS`
  list in `architecture.test.ts`, same risk class as the backend's
  `TABLE_OWNERS` — but self-detecting: the completeness test fails the moment
  a top-level `src/` folder is added, removed, or renamed without updating
  the lists (proven, §5).
- The regex-based import match (`from ['"](?:\.\./)+  (folder)(?:/|['"])`)
  detects standard relative ES-module imports as used consistently throughout
  this codebase (verified: no `require()`, no dynamic `import()`, no `.js`
  files exist in the checked directories). It would not catch an import
  disguised behind a path alias (e.g. a `tsconfig.json` `paths` mapping) —
  this project has none configured today (`tsconfig.json` inspected, no
  `paths` field), so the gap is currently theoretical.
- R9-as-originally-conceived remains unenforced, by design (§2), deferred to
  Phase 5.
- ESLint remains uninstalled. If a future need (more rules, IDE integration,
  a real second module's frontend) justifies it, this check can be
  re-expressed as an ESLint rule at that time without changing its intent.
