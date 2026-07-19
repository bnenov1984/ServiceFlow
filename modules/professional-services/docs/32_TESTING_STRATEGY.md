# PS-32 — Testing Strategy

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Rides the platform harness (pytest + uv backend, vitest frontend, CI as
exists); adds module suites. Rule inherited from the repo: business rules
([26]) are tested before UI exists (NFR-PS-25); the platform P0 list grows
with this module's isolation tests.

## T-1 Domain unit tests

Every BR/INV in [26] cites at least one test. Lifecycle matrix ([11] §2)
exhaustively: all state pairs × guard variants (valid, missing reason,
wrong role). Next-action rules N-1…N-9. Copy semantics ([12] §5): template
edit after instantiation leaves the assignment untouched.

## T-2 Deadline boundary tests (frozen clock)

The [13] §8 table is executable spec — each row a test case. Plus:
threshold-config edge (attention=urgent+1), no-deadline case, exact-time
minute boundary, breached→extended→normal transition, internal-vs-official
worse-of display rule. **Property test:** SQL read-model risk ≍ pure-engine
risk over generated assignments (the dual-implementation guard, [24] §3).

## T-3 Timezone tests

DST spring/fall pins ([13] §8); UTC-storage round-trip (write 23:30 Sofia
= 20:30 UTC summer, still "today" in Sofia); morning-job "today"
computation at 00:10 and 23:50 Sofia; year boundary (sequence rollover +
holiday table year switch).

## T-4 Inactivity tests

I-1…I-7 each: fires at threshold, not before; working-day arithmetic
across weekends + holiday-table days; I-4 suppression (appointment
present/past/absent); last_activity_at maintenance (which writes count —
communication yes, read no, notification no).

## T-5 Notification tests

Dedup: same evaluation twice ⇒ one row (unique dedup key); state
progression urgent→critical ⇒ second notification; auto-resolve on cause
removal; digest collapse (6 stale ⇒ 1 digest); breach not optable-out;
escalation timing (N-3, 2 days); snooze cut-through on state change.

## T-6 Permission tests

The [20] §3 matrix enumerated: every capability × every role, positive and
negative, server-side (route-level). Money shaping: worker without
visibility receives no money fields (absent, not nulled). Role-change
takes effect without re-login.

## T-7 Audit/immutability tests

Append-only enforcement: UPDATE/DELETE on `ps_activity_events` /
`ps_deadline_changes` fails at DB level even for the app role. Each
auditable action ([30] §5) produces its record with actor. Terminal revert
inside/outside 24 h.

## T-8 Isolation tests (P0 — release blocking)

Per platform practice: two tenants seeded; every `ps_*` table proven
invisible cross-tenant through the API **and** direct scoped-session
probes; RLS FORCE verified (owner role, superuser-bypass canary per
ADR-016's real-bug finding); number sequences and dedup keys scoped.

## T-9 Localisation tests

Catalog completeness both directions; label-pack substitution; no literal
Cyrillic from backend; date format parsing (`31.02.2026` rejected sanely).

## T-10 Integration/persistence/migration

API-level journey tests: J-1 (intake→number→defaults instantiated), J-3
(complete action→successor dialog contract), J-4 (requirement→received via
upload), J-5 (deliver→corrections→complete), follow-up linking. Migration
tests ride the platform's single-history harness; export-section round-trip
joins the ADR-012 CI harness when it exists (P0-8 dependency noted, not
duplicated).

## T-11 Frontend/UI tests

vitest component tests for: risk badge rendering (label+icon, never
colour-only assertion), quick-entry row interaction budget, N-4 successor
dialog paths, form state preservation on error. The Phase-2 architecture
test (`architecture.test.ts`) gains the ps-feature boundary case
([24] §4). Accessibility: axe checks on the ten screens' primary states;
keyboard traversal of S-3 and the S-4 next-action panel.

## T-12 High-risk edge cases (named, from analysis)

1. Official deadline today + delivered today ⇒ no breach notification
   (delivery stops the stream — [11] §5).
2. Assignment created with deadline in the past (backdated intake, S-3
   allows) ⇒ immediately breached, exactly one notification.
3. Next action completed at 23:59, successor declined, morning run ⇒
   no-next-action digest includes it once.
4. Template deleted (never used) vs deactivated (used) — pickers, existing
   assignments, Kanban template picker.
5. Owner deactivated in Core while owning 30 active assignments ⇒
   assignments stay valid, surface in "unassigned/orphaned owner" chip
   (INV-3 handling), reassignment flow works.
6. Two users complete the same next action concurrently ⇒ one wins,
   idempotent outcome, no duplicate successor prompt effects.
7. Holiday table missing for next year (job on 30.12) ⇒ working-day
   arithmetic degrades to weekends-only + health warning ([33]), never
   crashes.
8. Anonymization of a client with an active assignment ⇒ blocked with
   explanation (complete/cancel first) — rule surfaced here, normative in
   [16] §4.
9. Company with module deactivated mid-flight ⇒ routes 404 message-keyed,
   data intact, reactivation restores everything (BOS-06 lifecycle).
10. 5 000-assignment tenant: dashboard/list under NFR-PS-01 budgets
    (perf smoke, not micro-benchmark).
