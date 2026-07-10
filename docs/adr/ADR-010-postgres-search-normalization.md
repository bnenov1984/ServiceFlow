# ADR-010 — PostgreSQL Search with Domain Normalization

Status: **Accepted (architecture freeze)** · Date: 10.07.2026 · Source: 03 §D10, 02 §14

## Context
"Find any repair within seconds" across: customer name (Иван/Ivan must both hit),
phones (+359 88 123 4567 ≡ 0881234567), order №, IMEI, serial, VIN, рег. №. Volumes:
~15 k orders/year per installation.

## Decision
Search is served by PostgreSQL alone: **normalized shadow columns** maintained on
write (digits-only forms for phones/IMEI/VIN/рег. №; Cyrillic↔Latin transliteration
for names) + `pg_trgm` GIN indexes for fuzzy matching, combined in one ranked,
grouped query (Клиенти / Поръчки / Активи). Normalization rules live in the domain
(reused verbatim in SaaS). Budget: p95 ≤ 100 ms local.

## Alternatives considered
- **External engine (Elasticsearch/Meilisearch)** — a third service plus a sync
  pipeline for data that fits in RAM. Rejected; classic premature infrastructure.
- **Plain `LIKE` queries** — fails transliteration and formatting tolerance; table
  scans age badly. Rejected.

## Consequences
- **Advantages:** zero infrastructure; search correctness testable as pure domain
  logic; identical behavior in SaaS (per-tenant scoping added there).
- **Disadvantages:** shadow columns add write-path bookkeeping (encapsulated in one
  place); transliteration tables need Bulgarian-specific care (ж→zh, щ→sht…).
- **Risks:** ranking quality disappointing users. Mitigation: exact-identifier hits
  always rank first; pilot feedback tunes the rest.

## Reconsideration triggers
SaaS-scale cross-tenant analytics or faceted search needs (not V1/V2 launch scope).
