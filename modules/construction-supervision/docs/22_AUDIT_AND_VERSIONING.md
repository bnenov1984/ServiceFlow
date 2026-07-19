# CS-22 — Audit and Versioning

Status: Draft · Date: 18.07.2026

## 1. What is versioned, and how

| Artifact | Mechanism | Immutability point |
|---|---|---|
| Facts | append-only `cs_fact_versions` (author, reason) | every version immutable |
| Entity attributes (legally interesting) | same version+provenance mechanism | same |
| Generated documents | `cs_generated_versions`; drafts regenerable | **issuance**: snapshot + hash, trigger-protected; changes only via formal supersede(reason) |
| Templates | `cs_template_versions` (visual+manifest as one unit), effective dates | activation; retired versions retained forever (issued docs pin them) |
| Rules | versioned rule sets | active set swap; findings record rule version |
| Document type registry | versioned entries | in-place edits allowed only while no issued documents reference the entry; else new version |
| Extraction | batches record model id + prompt revision | append-only |
| Workflow/state | `cs_transitions` append-only log | every row |
| Timeline | `cs_timeline_events` projection | append-only |

## 2. Domain audit vs technical audit

- **Technical audit** (who logged in, admin actions) — Business OS Core's
  audit log (`identity` AuditLog), consumed via contract; not duplicated.
- **Domain audit** (who confirmed this fact, who issued this act, who waived
  this finding, why) — module-owned, embedded in the versioned structures
  above rather than a parallel "audit table" that could drift from the data
  it audits. The audit *is* the data model.

## 3. Snapshot discipline (the one sanctioned duplication)

ADR-CS-002 forbids duplicated *live* state. Issued-document snapshots are the
sanctioned exception class — copies by design, frozen at issuance, because
the legal record must show what was signed, not what is currently true.
Divergence between snapshots and live facts is *detected and surfaced*, never
auto-reconciled ([19 §3](19_VALIDATION_AND_CONSISTENCY.md)).

## 4. Answerable questions (acceptance yardstick for this design)

1. What did обр. 14 say when issued, and from which fact versions? (snapshot)
2. Who changed the permit issuer and why? (fact history)
3. Which documents show a value that changed since their issuance? (divergence findings)
4. What did the extraction propose vs what was accepted? (proposals retained)
5. Which template version produced this file, and does the stored hash match
   the bytes? (version pin + sha256)
6. What happened on the project between обр. 10 and обр. 11? (timeline)

## 5. Retention & export

Construction dossiers have decades-long legal relevance: no destructive
retention policies on issued documents, snapshots, or fact history. The
dossier export (roadmap E) bundles files + index + provenance + audit
extracts into a self-describing archive readable without the system —
extends the Business OS unified-export stance (ADR-012) with module content.
GDPR erasure requests are handled by anonymizing party personal data where
legally permitted while preserving document integrity — legal analysis
tracked in [29 Q5](29_RISKS_AND_OPEN_QUESTIONS.md).
