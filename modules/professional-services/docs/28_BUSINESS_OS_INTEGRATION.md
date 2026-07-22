# PS-28 — Business OS Integration

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

How the module fits the platform, point by commissioned point. The module
contract instance below follows BOS-06 (conceptual — no manifest file
format exists yet platform-wide).

## 1. Integration matrix

| Platform capability | Integration | Detail |
|---|---|---|
| Identity & authentication | consume | Core sessions/PIN/CSRF via `identity.deps`; no module auth of any kind |
| Organisations (tenancy) | consume | company = tenant = firm; ADR-016 regime on all `ps_*` tables |
| Users & roles | consume + extend | Core users + `is_owner`; module-scoped `ps_member_roles` ([20]) — module-private, not a platform RBAC |
| Clients | **own** | `ps_clients` per ADR-PS-003; no platform client capability exists to consume |
| Files & storage | consume port | ADR-007 storage port; module owns metadata tables |
| Notifications | **own** | first implementation on the platform (ADR-PS-009); extraction candidate later |
| Activity & audit | consume + own | platform AuditLog for security events; module-owned business activity ([30] §2) |
| Billing (subscriptions, ADR-018) | consume (Етап 3) | plan gating/read-only mode applies to this module like any other; nothing module-specific |
| Invoicing (commercial, Етап 4) | future contract | [21] §3 |
| Backup & restore | participate | export section per ADR-012/BOS-06 when the SaaS harness lands (FR-PS-121) |
| Localisation | consume mechanism | `ps.*` namespace; bg catalog; message-key errors (ADR-015) |
| Licensing / activation | participate | `company_modules` minimal activation (BOS-06): inactive ⇒ nav hidden, routes 404 with message key, seeds skipped |
| Installer / deployment | none | one artifact, SaaS (docs/14); module adds no deployment machinery |
| Shared UI shell | contribute | nav entries per [22] §2; shell owns chrome, module owns feature screens |
| Module navigation | contribute | via contract `navigation` when activation exists; hardcoded shell nav until then (platform's current state) |
| Global search | future contribute | module ships its own search sources now and declares them via the `search` module-contract field (BOS-06); Core owns the future facade — ownership and shape fixed by ADR-BOS-006, build itself still Deferred |
| Health | contribute | `ps_db_reachable` + job-freshness check ([33]) |
| Events | publish | `ps_*` catalogue ([09] §5) on the shared bus |

## 2. Module contract instance (conceptual, per BOS-06)

```yaml
# NOT IMPLEMENTED — declared properties of this module, BOS-06 shape.
id: professional-services            # package: professional_services
version: 0.1.0
core_api: 1
requires: []                         # Core is not listed (platform rule)
optional:
  - commercial                       # invoicing integration, post-MVP
  - construction-supervision         # assignment↔project links, [29]
tables: [ps_clients, ps_client_contacts, ps_service_types,
         ps_workflow_templates, ps_workflow_template_stages,
         ps_checklist_templates, ps_assignments, ps_assignment_stages,
         ps_assignment_members, ps_next_actions, ps_tasks,
         ps_document_requirements, ps_files, ps_communications,
         ps_payment_entries, ps_deadline_changes, ps_activity_events,
         ps_member_roles, ps_number_sequences, ps_notifications,
         ps_holiday_calendar, ps_assignment_links]
navigation:
  - {key: ps.nav.dashboard, route: /ps}
  - {key: ps.nav.assignments, route: /ps/assignments}
  - {key: ps.nav.clients, route: /ps/clients}
  - {key: ps.nav.workload, route: /ps/workload}
  - {key: ps.nav.notifications, route: /ps/notifications}
  - {key: ps.nav.settings, route: /ps/settings}
permissions: [ps.manager, ps.worker, ps.readonly]   # module-interpreted
i18n: {namespace: ps}
settings: [ps.assignment_label, ps.number_prefix, ps.threshold_attention,
           ps.threshold_urgent, ps.staleness_days, ps.waiting_days,
           ps.closeout_days, ps.worker_money_visibility,
           ps.personal_identifier_enabled]
health: [ps_db_reachable, ps_morning_job_fresh]
export: {section: professional-services, format_version: 1}
search:                  # declared per ADR-BOS-006; facade not built yet
  - {subject_type: assignment, fields: [number, title, client_name], route: /ps/assignments/{id}}
  - {subject_type: client, fields: [name, phones], route: /ps/clients/{id}}
events:
  publishes: [ps_assignment_created, ps_stage_changed,
              ps_lifecycle_changed, ps_next_action_set,
              ps_next_action_completed, ps_task_completed,
              ps_document_received, ps_file_added,
              ps_communication_logged, ps_deadline_changed,
              ps_payment_recorded]
  subscribes: [ps_*]                 # own activity writer only (MVP)
```

## 3. Platform work this module makes necessary (not performs)

Recorded for the roadmap ([35] Stage 0; decisions belong to the platform
process, not this module's docs):

1. **BOS-08 Phase 3** — Core package rename (`business_os.*`) before module
   code exists, so `professional_services` never imports `serviceflow.*`.
   Trigger condition ("PO commits to a second product") is met by
   committing to this module (CS's ADR-CS-001 claims the same trigger —
   either module's commitment suffices; both strengthen it).
2. **Minimal activation** — `company_modules` flag + nav gating (BOS-06
   lifecycle steps 4–5), because two verticals now coexist for real
   tenants.
3. **Event-bus neutral subject** — the `DomainEvent.order_id` fix lands at
   "the next natural touch" (BOS-02): the touch is now. One platform PR,
   before or with this module's first events.
4. **GDPR processor posture** (platform DPA, subprocessors list) — flagged
   for Етап-3 legal work; this module's data classes raise the stakes
   ([16] §4) but change nothing structurally.
5. **Global Search facade + Stable Event Naming discipline** (ADR-BOS-006/
   007) — informational only, no action required of this module: its event
   catalogue ([09] §5) already complies with the naming discipline, and its
   `search` contract section (§2 above) is already declared for whenever
   the facade is built.

## 4. What the module explicitly does not integrate with

ServiceFlow domain modules (no imports, no tables, no events consumed —
Separate Ways, [10] §2); ServiceFlow's frontend features; the parked local
installer; any external service (mail, calendars, messengers) in MVP.
