# CS-04 — Stakeholders and Roles

Status: Draft · Date: 18.07.2026

## 1. External stakeholders (people the documents are for)

| Stakeholder | Interest | Touches the system? |
|---|---|---|
| Supervision firm manager (управител, ДНСК удостоверение holder) | Legal liability for every signed act; firm efficiency | Yes — buyer, admin, signs most documents |
| Supervising engineers per part (специалисти СН from the МРРБ list) | Their names/credentials on acts; workload | Yes — daily users |
| Office/administrative staff | Assembling dossiers, chasing signatures | Yes — daily users |
| Client (възложител) | Correct, timely commissioning | Not in MVP (recipient of outputs); later: read-only portal (roadmap E) |
| Builder + technical manager | Signs acts; provides data (contracts, diplomas, dnевници) | Not in MVP; data about them, not accounts for them |
| Designers / authors' supervision | Sign acts per part | Same as builder |
| Municipality / главен архитект | Issues permits, commissioning certificates | No — paper/PDF interface only |
| ДНСК | Licenses consultants; inspects; ДПК for cat I–III | No — but audit trail is designed to survive their scrutiny |
| Testing labs / control bodies (органи за контрол) | Issue protocols the KB ingests | No |

Insight from samples: only the supervision firm's people are *users*. Everyone
else is *data* (participants) or a *recipient*. This keeps MVP authentication
scope inside one tenant — exactly the Business OS Core model.

## 2. Application roles (tenant-internal, MVP)

Built on Business OS identity (users, sessions, PIN switching — ADR-008),
consumed via `identity.deps`/`identity.contracts` only (BOS-16 boundary).

| Role | Permissions summary |
|---|---|
| **Owner/Manager** | Everything: manage projects, participants, users; confirm facts; issue documents; edit templates; resolve findings. |
| **Engineer** | Work on assigned projects: enter/confirm facts, run generation drafts, record acts, upload sources; cannot issue final documents or manage users/templates. |
| **Office** | Data entry: participants, source uploads, drafts; cannot confirm extracted facts of engineering nature or issue documents. |

Deliberately *not* modeled in MVP: per-part permission granularity (an El
engineer editing only Електро facts). Real firms are 1–10 people who trust
each other; the audit trail (who confirmed what) is the control, not ACLs.
Revisit only on client evidence ([29_RISKS Q6](29_RISKS_AND_OPEN_QUESTIONS.md)).
Detailed matrix: [23_SECURITY_AND_PERMISSIONS.md](23_SECURITY_AND_PERMISSIONS.md).

## 3. Signature vs. system action — a critical distinction

Acts are legally executed by *handwritten signatures on paper* (current
practice). The system therefore models:

- **"prepared"** — generated DOCX handed out for signing;
- **"issued"** — the firm records that the act was signed on date X (data
  snapshot frozen at this moment);
- optionally **"scanned copy attached"** — the signed paper's scan becomes a
  source document linked to the generated one.

The system never claims to *be* the signature. Qualified e-signature (КЕП)
integration is a distinct roadmap phase with its own legal analysis
([28_ROADMAP](28_IMPLEMENTATION_ROADMAP.md) Phase E, [29_RISKS Q5](29_RISKS_AND_OPEN_QUESTIONS.md)).

## 4. Participant registry vs. user accounts

Two different things, never merged:

- `users` (Business OS Core) — people who log in. Tenant-scoped.
- **participants** (this module) — legal actors on projects (firms, persons
  with credentials). They exist even when they never touch the system.
  A firm-level participant library (the builder you work with on five
  projects) avoids re-typing across projects — with per-project snapshotting
  of the attributes that were true at signing time
  ([07_DOMAIN_MODEL.md §4](07_DOMAIN_MODEL.md), [10_DATA_MODEL.md](10_DATA_MODEL.md)).
