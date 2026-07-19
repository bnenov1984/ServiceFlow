# PS-33 — Observability and Support

Status: **Draft for PO review** · Date: 18.07.2026 · Module: `professional-services`

Sized for one maintainer and small-firm tenants (NFR-PS-16). Consumes the
platform's logging/health plumbing; adds module signals only.

## 1. Health contributions (BOS-06 `health`)

- `ps_db_reachable` — trivial scoped query.
- `ps_morning_job_fresh` — last successful morning evaluation per tenant
  < 26 h ago; stale ⇒ degraded (the engine's outputs are the product; a
  silently dead job is the worst failure mode this module has).
- `ps_holiday_calendar_current` — next 60 days covered by a holiday table;
  else warning (edge case 7 in [32] T-12).

## 2. Logging & metrics

- Structured logs via platform logging; **no PII** (platform rule): ids,
  counts, durations, message keys — never titles, names, notes.
- Module metrics worth having from day one (log-derived counters suffice;
  no metrics stack is added): morning-run duration + assignments evaluated
  per tenant; notifications generated/deduped ratio (an exploding ratio =
  dedup bug); API error-rate by message key (top keys = UX problems).

## 3. Supportability features (cheap, high-leverage)

- Every assignment's История tab is the support tool: "какво се случи"
  answers itself without DB access.
- The engine's determinism (INV-9) means support can reproduce any warning
  locally from an export — no "it flashed red yesterday" archaeology.
- Org settings screen shows effective thresholds + holiday table — support
  and users see identical truths.
- Error responses carry message keys that map 1:1 to catalog + docs —
  supportable over the phone ("какво пише точно?").

## 4. Diagnostics deliberately not built

No per-tenant dashboards for the operator, no tracing infra, no alerting
stack beyond platform health — additions ride Етап-3 platform admin work
if/when it defines them. The module keeps its part cheap: honest health
hooks and reproducible state.
