# CS-18 — Quantity Calculation Engine

Status: Draft · Date: 18.07.2026 · Phase D capability. Deterministic by
definition — no AI anywhere in this engine.

## 1. Purpose

Given structural elements with geometry (from schedules, drawings, or manual
entry), compute the quantities the acts declare:

- **Concrete** (m³) per element / pour / level: volumes from typed geometry
  (footing prism, column h×b×l, wall area×thickness, slab area×thickness).
- **Formwork** (m²): contact surfaces per element kind (the sample обр. 7
  declares "Кофраж 164 кв.м" — reproducible from element faces).
- **Reinforcement** (kg, by steel class and diameter): from rebar schedules —
  bar lengths × unit mass (Ф6.5/Ф8/Ф12/Ф14/Ф16… as in the sample's
  m/kg paired tables); schedule totals cross-checked against per-bar sums.

## 2. Design

- **Formula registry in code**: each metric per element kind is a pure, unit-
  tested function with an explicit formula key; `cs_quantity_lines` records
  formula key + inputs + result, so every number is re-derivable and
  explainable ("26 m³ = Σ footing volumes F1–F8, inputs …").
- **Units discipline**: quantities are `numeric` + unit from a closed
  vocabulary; conversions centralized; rounding rules declared per metric
  (concrete to 0.5 m³ practice vs exact — configurable, recorded).
- **Aggregation axes**: element → pour/act scope → level → project part →
  project. Act tables bind to the *scope* aggregate (the обр. 12 for
  "армировка основи" pulls exactly the foundation-level rebar lines).

## 3. Three-way comparison (where the value is)

For any scope: **computed** (this engine) vs **extracted** (drawings/
schedules claims) vs **declared** (what acts say — project & изпълнено
columns). `quantity_tolerance` rules ([13 §2](13_RULES_ENGINE.md)) compare
with per-metric tolerances → findings, never silent correction. The sample's
identical проектно/изпълнено columns suggest declared values are often
copied, not measured — exactly the practice this comparison illuminates for
the supervising engineer *before* signing.

## 4. Honesty limits

The engine computes what geometry supports. Laps, waste, chairs/spacers,
concrete over-pour are practice factors — supported as declared coefficients
per metric (visible in the formula record), never invented. Where inputs are
absent, there is no number — a missing quantity is a finding, not an estimate
(consistent with "never invent values").
