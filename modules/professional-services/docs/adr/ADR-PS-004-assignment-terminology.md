# ADR-PS-004 — "Assignment" internal term + configurable visible label

Status: **Proposed** · Date: 18.07.2026

## Context

The core object needed a neutral internal term (`WorkOrder`, `Engagement`,
`Assignment`, …) with an org-configurable Bulgarian visible name (Поръчка /
Възлагане / Досие / Преписка / …), stable internally regardless of label.
Candidates weighed: **WorkOrder** — collides conceptually with
ServiceFlow's ServiceOrder and trips the platform's anti-goal #2 optics
(generic entity names); **Engagement** — precise professional-services
industry term, but weakly translatable (ангажимент is colloquial) and
unfamiliar to the personas; **Case** — collides with court cases inside the
court-expertise data itself; **Dossier** — names the file, not the work.

## Decision

- Internal domain term: **`Assignment`** — neutral, translation-natural
  (възлагане/поръчка), no collision with either neighbouring module.
- Visible name: org setting **label pack** from a closed list with correct
  Bulgarian forms (PS-31 §2); default „Поръчка". Free-text packs deferred.
- i18n keys always use the internal term (`ps.assignment.*`); catalog
  strings interpolate the pack. Glossary rule PS-04 §4.1 makes this
  binding for all copy.
- "Задача" is selectable as a label but the settings UI warns about the
  Task collision.

## Consequences

- Docs, schema (`ps_assignments`), API, and events are permanently
  label-independent; a label change is a settings write, nothing else.
- The closed-list pack approach trades ultimate flexibility for
  grammatical correctness — the right trade for the persona set; the
  free-text escape hatch stays on the P list with its imperfection
  explicitly priced.
