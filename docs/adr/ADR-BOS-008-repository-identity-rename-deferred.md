# ADR-BOS-008 — Repository Identity: Rename from ServiceFlow to BusinessOS (Deferred)

Status: **Deferred** (decision recorded now; execution postponed to a
stated trigger — not "Accepted", because nothing is executed by this ADR)
· Date: 21.07.2026 · Source: PO review of docs/business-os +
modules/professional-services (this session)

## Context

The repository root/folder and GitHub repository are both named
`ServiceFlow`, chosen when ServiceFlow was the only product. The
repository now hosts: Business OS Core (identity/tenancy/platform,
currently still under the `serviceflow.*` package pending
[08_EVOLUTION_ROADMAP.md](../business-os/08_EVOLUTION_ROADMAP.md) Phase 3),
the ServiceFlow vertical itself, Professional Services (Phase-0 docs,
`modules/professional-services/`), Construction Documentation (Phase-0
docs, `modules/construction-supervision/`), and Commercial Documents
(in-progress code, `commercial/`).

An outer folder/repo named `ServiceFlow` risks reinforcing an incorrect
mental model — that Professional Services or Construction Documentation
"live inside ServiceFlow" — when architecturally they are siblings under
Business OS Core (BOS-00 §2, §4). This is a **different naming layer**
from BOS-08 Phase 3, which renames the *Python package*
(`serviceflow.identity` → `business_os.identity`); this ADR concerns the
*repository/folder* identity, one level up, untouched by any existing
roadmap phase.

## Decision

1. **Target identity, recorded now:** the eventual repository root name is
   **`BusinessOS`** (folder + GitHub repo), with the shape:
   ```
   BusinessOS/
   ├── backend/
   │   ├── business_os/
   │   └── serviceflow/
   ├── frontend/
   ├── modules/
   │   ├── professional-services/
   │   └── construction-supervision/
   └── docs/
       └── business-os/
   ```
2. **Not executed by this ADR.** No folder move, no GitHub rename, no
   path rewrites happen now. Renaming today would be mechanical churn
   (high file count, zero functional benefit) ahead of the code-level
   rename it should logically follow, and orthogonal to any current
   Stage-0 platform work.
3. **Trigger and sequencing:** execute no earlier than, and in the same
   wave as, **BOS-08 Phase 3** (Core package rename). Renaming the outer
   folder before the inner package would move the confusion rather than
   resolve it — the code would still say `serviceflow.*` inside a folder
   called `BusinessOS`. Recommended order: (a) Phase 3 code rename lands;
   (b) repository/folder/GitHub rename follows immediately after, once a
   second module has **real code** (not just Phase-0 docs) — the same
   condition Phase 3 itself already uses ("PO commits to a second
   product… or Етап 3 platform work starts colliding with ServiceFlow
   naming in practice").
4. **Until executed**, this document is the explicit acknowledgment that
   the outer name is a known, accepted mismatch — not an oversight.
   [modules/professional-services/docs/36_RISKS_AND_OPEN_QUESTIONS.md](../../modules/professional-services/docs/36_RISKS_AND_OPEN_QUESTIONS.md)
   A-1 and [modules/professional-services/docs/adr/ADR-PS-001](../../modules/professional-services/docs/adr/ADR-PS-001-module-identity-and-location.md)
   already state the outer directory name is "not architecturally
   authoritative" — this ADR is the decision record that statement was
   pointing at.
5. **Mechanics when executed** (recorded for later, not decided in
   detail): GitHub repo rename (GitHub preserves redirects automatically);
   each developer renames their local clone folder (mechanical, no server
   action); a grep-based sweep for any hardcoded absolute path references
   in docs/scripts. No claim is made here that zero such references
   exist — that check happens at execution time, not now.

## Alternatives considered

- **(a) Rename now** — rejected: pure churn ahead of the code-level rename
  it should follow; risks disrupting in-flight branches for no functional
  gain today.
- **(b) Never rename** — rejected: the folder name actively reinforces a
  wrong mental model, and the mismatch compounds as more verticals are
  documented or built.
- **(c) Rename the folder/repo now but leave the Python package
  `serviceflow.*` unchanged** — rejected as a confusing half-step (folder
  says `BusinessOS`, code still says `serviceflow`); better to execute
  both renames in one coordinated wave when the trigger fires.

## Consequences

- No immediate work; the folder/repo name remains `ServiceFlow` until the
  trigger fires.
- The mismatch is now a **documented, deliberate deferral**, not a silent
  gap — future readers of this ADR know both the plan and the trigger.
- `modules/professional-services/docs/36` A-1 gains a citation to this ADR
  (see companion edit) so the two documents do not separately re-litigate
  the same naming question.

## Reconsideration triggers

Identical to BOS-08 Phase 3's own trigger. Do not execute early; do not
execute the folder/repo rename separately from the Phase-3 code rename.
