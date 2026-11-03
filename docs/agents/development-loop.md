# Agent Development Loop

This is the repository's operational control loop for AI-assisted development. It complements the architectural rules in the root CLAUDE.md.

## Core principle

**One work unit → one verification checkpoint → one commit.**

A work unit is one independently verifiable logical change from a .scratch/<feature>/issues/NN-*.md ticket or an explicitly scoped maintenance task. Do not silently expand the work unit.

## Before editing

1. Inspect git status --short and classify any pre-existing changes. Never overwrite, revert, or absorb unrelated work.
2. Read the relevant .scratch spec/ticket, docs/INDEX.md, applicable ADRs/domain docs, and the nearest CLAUDE.md.
3. State the current work unit, its scope, out-of-scope items, acceptance criteria, and intended verification.
4. If the work is multi-file or architectural, use Plan mode first.
5. If the requested work cannot fit a small independently verifiable checkpoint, split it before editing.

## During editing

- Work only inside the declared work unit.
- Do not opportunistically refactor, rename, format, or clean up unrelated code.
- If a dependency or design issue expands the scope, stop and record the new issue/slice instead of silently continuing.
- Keep the diff reviewable. As a default warning threshold, stop and re-scope at **10 changed files or 300 changed lines** unless the larger diff is mechanical and explicitly part of the same acceptance criterion.
- Do not carry unrelated uncommitted changes into the checkpoint.

## Checkpoint

Before starting another work unit:

1. Run the smallest relevant tests.
2. Run relevant static checks; for cross-cutting backend changes include ruff, mypy, and lint-imports when applicable.
3. Run git diff --check.
4. Inspect git diff --stat and the complete diff for scope contamination.
5. Verify acceptance criteria and applicable architecture rules.
6. Commit the completed work unit with a conventional, specific message.
7. Leave the working tree clean unless an explicitly documented next-step artifact is intentionally left.

**Commit is automatic after a passed checkpoint. Push is not automatic.** Pushing requires explicit user authorization.

## Session boundary

End the session after a completed checkpoint when:
- the work unit is committed;
- the next work unit is materially different;
- context is becoming unreliable;
- or the task has expanded enough to require re-planning.

Use a handoff artifact for the next session rather than relying on chat history.

## Failure rule

If verification fails, remain inside the current work unit. Fix only the cause relevant to that checkpoint, re-run verification, and do not start another feature until the checkpoint is green.

## Emergency stop

If the diff unexpectedly crosses the scope boundary, stop editing. Report:
- intended files;
- actual changed files;
- why the scope expanded;
- tests run;
- the safest next action.

Do not finish everything while you're here.