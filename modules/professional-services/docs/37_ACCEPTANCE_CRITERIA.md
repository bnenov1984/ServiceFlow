# PS-37 — Acceptance Criteria

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

MVP exit gate. Written as verifiable statements (given/when/then style
compressed); each maps to FRs and tests via [38]. The gate is **all of
§1–§5 plus the P0 set green**.

## 1. Journey criteria (the backbone)

- **AC-1 (J-1):** A first-day user creates a client inline and an
  assignment (title, service type, official deadline) in ≤60 s; the
  assignment has a unique number, the type's workflow stages, checklist
  and document requirements instantiated; the next-action prompt appears
  on save; declining it lands the assignment in the no-next-action bucket
  by next morning run.
- **AC-2 (J-2):** With seeded data containing each risk/inactivity state,
  the dashboard shows all nine buckets with exact counts; every bucket
  drills into a correctly filtered list; every listed state carries label
  + icon (verified without colour).
- **AC-3 (J-3):** Completing a next action always presents the successor
  choice; each of the three paths (new action / stage change / explicit
  none) leaves the recorded trace and correct bucket membership.
- **AC-4 (J-4):** A requirement moved to received via file upload clears
  the assignment from the waiting-documents bucket iff no other
  missing/requested requirement remains.
- **AC-5 (J-5):** Deliver requires delivery fields; delivered assignments
  stop breach warnings and start close-out staleness; corrections return
  is reasoned and historised; complete freezes the record per INV-12;
  follow-up creation links bidirectionally and copies no deadlines/money.

## 2. Engine criteria

- **AC-6:** The [13] §8 boundary table passes exactly, including the DST
  pin, with a frozen clock.
- **AC-7:** Changing an official deadline without a reason is impossible
  through the API; the change history shows old, new, reason, actor, time;
  extension clears breach while history persists.
- **AC-8:** Recomputing all risk/staleness states from a tenant export
  reproduces the live states byte-for-byte (INV-9 demonstration).
- **AC-9:** I-4: an assignment whose only future event is an
  appointment-flagged next action never appears stale; removing the
  appointment surfaces it at the correct threshold.

## 3. Notification criteria

- **AC-10:** Running the morning evaluation twice produces zero duplicate
  notifications; urgent→critical produces exactly one new one; resolving
  the cause auto-resolves live notifications.
- **AC-11:** Six stale assignments for one user yield one digest; a
  breached official deadline yields individual critical notifications to
  owner + managers and cannot be opted out.

## 4. Control criteria

- **AC-12:** The [20] §3 matrix holds server-side for every capability ×
  role (negative tests included); money fields are absent from responses
  to non-visible roles.
- **AC-13:** Every auditable action ([30] §5) demonstrably writes its
  record; UPDATE/DELETE on append-only tables fails at the DB level.
- **AC-14:** Cross-tenant: no `ps_*` row, file, notification, or search
  result crosses tenants under the full P0 isolation suite.

## 5. Product-quality criteria

- **AC-15:** All ten screens function per [23] including empty/loading/
  error states; org label substitution leaks no `{label}` placeholders;
  no untranslated key renders.
- **AC-16:** Narrow-screen: S-1, my-work S-2, S-4 quick actions, S-10
  usable at 360 px; axe checks pass on the ten screens' primary states.
- **AC-17:** Seeded 5 000-assignment tenant meets NFR-PS-01/02 budgets.
- **AC-18:** The three worked examples ([../examples/](../examples/))
  are enterable end-to-end through the UI using only shipped starter
  templates, without schema or code changes — the generic-model proof.

## 6. Pilot acceptance (Stage 6, beyond MVP gate)

≥1 real firm keeps its register current for 14 consecutive days
(entries/user/day metric — R-4); zero missed official deadlines among
register-current assignments during the pilot; PO sign-off against [00] §6.
