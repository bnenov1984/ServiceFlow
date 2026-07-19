# CS-15 — Document Generation Pipeline

Status: Draft · Date: 18.07.2026 · The outbound half of the system
([09 §3.2](09_SYSTEM_ARCHITECTURE.md)); template mechanics in
[12_TEMPLATE_ENGINE.md](12_TEMPLATE_ENGINE.md).

## 1. Stages

```
1 SELECT    document type + instance context
            (project, part, instance label, date, participants override?)
2 RESOLVE   manifest bindings → values
            • entity attrs (permit, participations valid at date)
            • KB facts (confirmed only — proposals invisible here)
            • composed sources (dossier inventory, works tables)
            • calculated fields (calc registry)
3 VALIDATE  rule set for the type + gate rules
            → blockers ⇒ STOP, return findings (message keys)
            → warnings ⇒ surface, allow continue
4 RENDER    deterministic substitution into the visual template version
            → DOCX draft (normalized, hashed)
5 REVIEW    human looks at the actual document; loops to fix facts →
            regenerate (cheap, stateless)
6 PREPARE   content lock for signing (hash pinned; regeneration = new cycle)
7 ISSUE     record signed date + number → DataSnapshot (facts, participant
            attributes, template version, file hash) → immutable version
            → events (timeline, dossier, gates)
```

## 2. Properties enforced per stage

- **2 RESOLVE** never reads proposals or unconfirmed data; participants are
  resolved *as of the document date* (builder-change correctness).
- **3 VALIDATE** is the only gatekeeper; rendering cannot be reached with
  blockers (no "generate anyway" backdoor — NFR-2). Missing soft fields render
  as explicit visible markers (▯▯▯), never silent blanks, and always carry a
  warning finding.
- **4 RENDER** is pure: no I/O beyond template fetch, no clock (document date
  is an input), no AI. Renders are reproducible byte-for-byte (NFR-1) —
  CI golden tests per template version.
- **7 ISSUE** is transactional: snapshot + state + number + events commit
  together or not at all. Issued versions are trigger-protected
  ([10 §4](10_DATA_MODEL.md)).

## 3. Instance families & series

Recurring types (обр. 12/7/8): instance label + automatic sequence within
type+project. Numbering of *issued* documents per firm practice (№ per
project per type, e.g. Акт обр.12 №5) — sequence semantics live in the
registry; the open ownership question for cross-module numbering
infrastructure is tracked in [24 §4](24_INTEGRATION_WITH_BUSINESS_OS.md).

## 4. Snapshot contents (what "frozen" means)

`data_snapshot` = the *resolved context* of stage 2 at issue time: every
bound value with its fact version id / entity attribute copy, participant
block as rendered, template version id, calc inputs. Enough to (a) re-render
the identical document forever, (b) answer "why does the issued act say X",
(c) diff a superseding version against its predecessor field-by-field
([22](22_AUDIT_AND_VERSIONING.md)).

## 5. Outputs

- DOCX always (the legal/practice format — firms print and sign).
- PDF derivative for preview/archive (LibreOffice headless server-side) —
  convenience artifact, the DOCX hash is the artifact of record.
- Later (roadmap E): batch generation (all missing acts for a phase),
  dossier export bundle ([FR-10.1](05_FUNCTIONAL_REQUIREMENTS.md)).
