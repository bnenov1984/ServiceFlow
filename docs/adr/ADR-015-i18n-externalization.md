# ADR-015 — i18n Externalization, Bulgarian-Only Launch

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §3, blueprint Part 2

## Context
Bulgarian is the product language and the UI must speak Bulgarian business language
(„Чака части", never "Procurement state"). English and other languages are future
market options, and retrofitting i18n into a string-hardcoded UI is a full rewrite
of every screen.

## Decision
Every user-facing string is externalized from the first component: key-based catalog
(ICU message format) on the frontend; the backend emits **message codes + parameters,
never prose** (the UI renders them). Bulgarian is the only shipped catalog in V1 and
the permanent fallback. Formats frozen for V1: DD.MM.YYYY, 24-hour, Europe/Sofia
presentation over UTC storage (C6), EUR via the currency abstraction (Q3 decision),
Bulgarian number formatting. Three layers stay separated (never mixed): system UI
translations · company-configurable business terms (e.g. protocol terms text) ·
user-entered content.

## Alternatives considered
- **Hardcode Bulgarian, i18n later** — cheapest today; a rewrite of every screen and
  every backend message the day a second market appears. Rejected.
- **Ship bilingual (BG+EN) now** — doubles translation maintenance during the
  fastest-churn period of the UI for zero paying users. Rejected; keys make EN a
  catalog drop later.
- **Backend-rendered translated strings** — couples API responses to a locale,
  breaks caching and SaaS multi-locale reuse. Rejected.

## Consequences
- **Advantages:** language expansion is content work, not engineering; enforced
  separation keeps legal texts (protocol/invoice) company-editable without touching
  translations.
- **Disadvantages:** key discipline has ongoing cost (naming, orphan cleanup);
  developers see keys, not text, in code.
- **Risks:** untranslated-key leakage to users. Mitigation: CI check — no literal
  user-facing strings in components, no missing catalog entries.

## Reconsideration triggers
Second-market launch adds catalogs and possibly per-company language preference
(schema-ready via company settings); the architecture does not change.
