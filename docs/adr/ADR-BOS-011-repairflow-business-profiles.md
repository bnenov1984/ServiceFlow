# ADR-BOS-011 — RepairFlow Business Profiles

Status: **Proposed (audit-driven, 26.07.2026) — awaiting PO review; not part of
the frozen ADR set. Profile-ownership corrected 26.07.2026 by PO
clarification 1: the initial profile is vendor-assigned at provisioning, not
a tenant preference — see §Decision 1/3/7.** · Source: docs/business-os/18
(audit), frozen product model (26.07.2026 PO directive), ADR-CS-007
(registry-as-data precedent, modules/construction-supervision), docs/08 §4
(EAV rejection)

## Context

The frozen product model states automotive repair, phone repair, electronics
repair, appliance repair are **configurations of RepairFlow**, not separate
products — RepairFlow must never fork by industry. Today's code already has
the right shape for this, just not scoped correctly: `AssetType` (migration
0003) is a **global**, company-agnostic seed table — `code` is a bare primary
key, `field_defs` (JSONB: `{key, label_bg, type, choices?, identifier_kind?}`)
is identical for every tenant, seeded once. Every company sees the same four
types (`phone`, `vehicle`, `laptop`, `other`) with the same fields. There is
no per-company variation mechanism anywhere in the asset system today.
`validate_field_values` (`assets/service.py`) already validates strictly
against whatever `field_defs` the resolved `AssetType` carries — the
validation *mechanism* needs no change, only what it resolves against.

## Decision

1. **What a business profile is — four negative/positive definitions,
   stated explicitly because each rules out a plausible wrong reading:**
   - **Not an application entitlement.** It answers "how does RepairFlow
     behave for this company," never "does this company have RepairFlow"
     (that question is ADR-BOS-010's alone). Assigning or changing a profile
     never touches `companies.settings.active_modules`, and entitling
     RepairFlow never implies a profile.
   - **Not a normal tenant preference.** Unlike warranty defaults, status
     renames or workflow templates — which a Tenant Owner changes freely,
     at will, with no external approval — a profile determines the *shape of
     the data model* the company's assets are validated against. It is
     assigned, not chosen, and changed by exception, not by preference (§7).
   - **RepairFlow-specific.** It is scoped to one module (§3), never a
     company-wide platform attribute, and no other module inherits or
     observes it.
   - **Initially vendor-assigned during company provisioning** (§Decision 3).
2. **Profile identifier**: a stable lowercase slug, one of
   `automotive_repair | phone_repair | electronics_repair | appliance_repair
   | generic_repair`, stored at `companies.settings.repairflow.business_profile`
   — the existing JSONB-settings pattern (docs/business-os/02: "keep JSONB,
   reject a settings registry/schema system now"), not a new mechanism.
   `generic_repair` is the default and is exactly today's shipped behavior
   (the current four-type seed set) — **no existing tenant's behavior changes
   on migration day**.
3. **Ownership — assignment vs. configuration, split between the two planes:**

   | Concern | Owner | When |
   |---|---|---|
   | **Assigning** the initial profile | **Vendor Administrator** | During company provisioning (ADR-BOS-009 workstream 2) — the profile is chosen with the customer, at sale/onboarding time, and set alongside entitlements |
   | **Configuring** within the assigned profile — workflow templates, status renames, warranty defaults, and any other application setting the profile permits | **Tenant Owner** | Freely, at any time, no vendor involvement |
   | **Changing** the profile after operational data exists | **Vendor Administrator**, on tenant request, after compatibility review | By exception only (§7) |

   A Tenant Owner **may request** a profile change and **may not** perform
   one. Before any operational data exists there is nothing to migrate, so a
   vendor administrator can simply reassign; after assets/orders exist the
   controlled-migration path in §7 applies. The tenant-facing UI therefore
   shows the assigned profile **read-only**, with a "request a change"
   affordance that opens a support conversation — never a live selector.

   **Module scope**: RepairFlow-scoped, not company-wide and not Core.
   Nothing outside RepairFlow has an asset-type concept today (PropertyFlow's
   engagements have no equivalent need — docs/business-os/02's Group-D
   discipline: don't generalize for one consumer). If a second module ever
   needs a comparable per-company field-set mechanism, that module designs
   its own; extraction only happens from two real implementations
   (docs/business-os/08 Phase 6 rule), never from one plus a guess.
4. **What a profile controls**: exactly what `field_defs` already
   expresses — which asset types are visible, per-field visibility/
   required-ness/validation/choices, and Bulgarian terminology
   (`label_bg`/`name_bg`), plus each profile's **default** workflow
   template/status set at asset-type-selection time. It does **not**
   introduce a new validation-rule language or a no-code field builder — the
   existing `{key, label_bg, type, choices?, identifier_kind?}` vocabulary is
   reused verbatim. A profile is a *named, curated instance* of that
   vocabulary, not a second schema next to it.
5. **Asset types become per-company, seeded at profile assignment —
   the one real schema change this ADR implies** (not authored here; see
   docs/business-os/18 §6). `asset_types` moves from a bare global `code`
   primary key to company-scoped rows, seeded once when a vendor
   administrator assigns the company's profile during provisioning (default
   `generic_repair` seeded for every existing company on the migration that
   introduces this, so it is a no-op for current tenants) — the same
   copy-on-create discipline `ps_assignment_stages` already uses for
   workflow-template stages (ADR-PS-005: "stage copies, not template
   references"), reused here for asset-type copies instead of invented fresh.

   **Amended 03.11.2026 (order-workflow-revamp WP-C, Q18, migration 0034):**
   a profile seeds **exactly one** asset type, not four identical ones — so
   intake shows no type picker for a company with the usual single type.
   Seed map: `automotive_repair` → Автомобил (unchanged code/fields) ·
   `phone_repair` → Телефон / таблет (existing "phone" code, gains a "вид"
   choice field) · `electronics_repair` → Устройство (new) ·
   `appliance_repair` → Уред (new) · `generic_repair` → Друго (unchanged
   code/fields). Existing companies: a no-longer-matching type is replaced
   outright where safe (no order ever referenced its assets — `service_
   orders.asset_id` has no `ON DELETE` clause, so a real reference blocks
   the delete rather than cascading through it); a company left holding
   more than one type after that is real cross-type order history the
   migration correctly left alone, not a bug — it keeps seeing the picker
   until reconciled by hand.

   **Amended 04.11.2026 (order-workflow-revamp WP-H, Q16/Q16b, migration
   0036):** each asset type also carries an `accessories: bool` flag —
   true for every profile's type except automotive's "vehicle" (migration
   0036 sets it false there, backfilled from `business_profile`). This
   moves accessories from §Decision 8's "stays common across every
   profile" list to an asset-type property, same as the five profile
   identifiers themselves — see §8's amendment below.
6. **Backend validation is authoritative, not the frontend picker.** A
   company's active asset types/fields are resolved and enforced
   server-side on every asset create/update, exactly as today — a profile
   is not allowed to be a frontend-only filter over a still-global backend
   list (same "backend guards are mandatory" principle as ADR-BOS-010 §2).
7. **Changing profile after operational data exists is a controlled
   migration, not a setting toggle.** Two distinct cases:

   - **Before any operational data exists** (no assets, no orders): a
     vendor administrator reassigns the profile directly. The seeded
     asset-type rows are replaced; nothing references them yet, so there is
     nothing to migrate.
   - **After assets/orders exist**: the change requires (a) a tenant
     request, (b) a **compatibility review** — which existing asset types
     and `field_values` keys exist in the current profile but not the
     target, i.e. what would stop being offered on new assets — and (c)
     **explicit vendor approval**. It is executed by a vendor
     administrator, never self-served, and is recorded append-only with
     actor, old profile, new profile, reason, and the compatibility-review
     outcome (the same reasoned-change shape `PSDeadlineChange` already
     established, reused rather than invented; the record lives in
     `platform_audit_log` per ADR-BOS-009 since the actor is a vendor
     administrator).

   In **both** cases the change is **non-destructive**: it never deletes or
   reinterprets existing `assets.field_values`. Historical assets keep
   exactly the field values they were saved with regardless of what the
   *current* profile's `field_defs` says — the same tolerance the code
   already has for any asset-type field no longer present in a def (unknown
   keys are simply not rendered, never dropped from storage). Only assets
   created *after* the change follow the new profile. No automatic
   backfill or reinterpretation is ever attempted; the compatibility review
   exists to make the consequences visible before the change, not to
   authorize a data rewrite after it.
8. **What stays common across every profile, always**: the entire frozen
   domain model — customers, orders, the status transition matrix, diagnosis,
   parts/labor, protocol PDF, invoicing (docs/01/02, BR-1…BR-10). A profile
   varies *asset fields and terminology only*. The moment a "profile" needs
   a different workflow engine or a different aggregate, it is not a
   RepairFlow profile — it is a signal for a real second module, restated
   from the frozen product model itself.

   **Amended 04.11.2026 (WP-H, Q16/Q16b):** accessories is no longer on
   this "stays common" list — it is now a per-asset-type `accessories`
   flag (§Decision 5's amendment), off for automotive only. Nothing about
   the accessories *data model* (AccessoryItem, the order-level checklist
   mechanism itself) varies by profile — only whether a given profile's
   type offers it at all, the same kind of per-type variation `field_defs`
   already provides for ordinary fields.

## Alternatives considered

- **Generic no-code profile/field builder** (tenant defines arbitrary fields
  per asset type) — explicitly out of scope (task constraint) and directly
  contradicts docs/08 §4's standing EAV rejection. Rejected.
- **A brand-new `business_profiles` domain model with its own rule DSL** —
  rejected: `field_defs` JSONB is already this mechanism, just not
  company-scoped; a second parallel mechanism duplicates a decision docs/08
  §4 already made.
- **Keep `asset_types` global, vary only frontend field visibility per
  profile** — rejected: a field hidden in the UI but still accepted by the
  backend is a validation gap, the same bug class ADR-BOS-010 rejects for
  entitlement checks. The backend must resolve and enforce the active
  profile's fields itself.
- **Profile as a Core/platform concept** — rejected; no second consumer
  exists (docs/business-os/00 §7 anti-goal #2: no generic entity replacing a
  concrete one without a second product on the roadmap in code).
- **Tenant Owner freely switches profile like any other setting** —
  **rejected by PO clarification (26.07.2026)**, and correctly so: a profile
  determines which asset types/fields exist, so a free switch after
  operational data exists silently changes what future assets can record
  while leaving historical assets in a shape the current profile no longer
  describes. That is a data-model migration wearing a preference toggle's
  clothing. The controlled path (§Decision 7) keeps the capability without
  the footgun. *(This was the original draft's position; it is superseded.)*
- **Vendor owns profile configuration too** (workflow templates, statuses,
  warranty defaults inside the profile) — rejected: that would make the
  vendor a bottleneck for ordinary day-to-day tenant administration, which
  contradicts the accepted model's own split (vendor owns commercial/
  structural facts, tenant owns operational configuration).

## Consequences

- `asset_types` needs a real migration (company-scoping + profile seed
  logic) before this ADR is anything but paper — **not implemented by this
  ADR**, proposed schema in docs/business-os/18 §6, requires explicit
  approval per this task's Phase 4 rule.
- Existing seed/test fixtures that assume a global `asset_types.code` (e.g.
  `backend/tests/test_assets.py`, `backend/migrations/versions/0003_assets.py`)
  need updating in the same migration PR, not as a follow-up.
- Intake-flow validation code (`assets/service.py::validate_field_values`)
  needs no logic change, only a company-scoped lookup instead of a global one
  — the risk surface of this change is the migration and the lookup call
  sites, not the validation rules themselves.
- RepairFlow's five profile identifiers become part of the frozen
  vocabulary the same way order statuses are (reviewed like code when
  changed, ADR-CS-007's "the registry becomes review-worthy data" precedent).
- **The Vendor Console gains a provisioning-time responsibility**: profile
  selection is part of creating a company (ADR-BOS-009 workstream 2), not a
  later optional step — a company cannot be provisioned without one, and
  `generic_repair` is the explicit default rather than an empty/NULL state.
- **The tenant settings UI shows the profile read-only** with a request
  affordance, never a selector — a frontend consequence that must not be
  "simplified" into a dropdown later (the same
  backend-enforcement-over-UI-affordance discipline as §Decision 6).
- **A profile change needs a compatibility-review step before it is
  executable** — a small vendor-side diff (which asset types/fields exist
  in the current profile but not the target) that must exist before the
  change action is offered at all.

## Reconsideration triggers

A profile candidate that needs a different *workflow*, not just different
*asset fields* (build a real module instead, don't stretch this ADR to
cover it); evidence that the shared `field_defs` shape stops being
expressive enough across profiles (none today).
