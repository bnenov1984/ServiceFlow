---
name: checkpoint
description: Finish the current BusinessOS work unit safely. Use after a logical change is implemented or when the user asks to checkpoint, commit, or verify the current slice.
---

# /checkpoint

Treat the current change as a controlled checkpoint, not as permission to continue coding.

## Procedure

1. Read the current work-unit scope from the active .scratch ticket/handoff and inspect git status --short.
2. Confirm that only intended files changed. If unrelated changes are present, do not stage them.
3. Run the smallest relevant tests first.
4. Run applicable static checks:
   - backend: uv run ruff check ., uv run mypy, uv run lint-imports when relevant;
   - frontend: relevant Vitest tests and npm run build when the change affects the production build;
   - E2E when the acceptance criterion is an end-to-end journey.
5. Run git diff --check.
6. Review git diff --stat and the complete diff against the acceptance criteria and architecture rules.
7. If green, stage only the files belonging to this work unit and create one conventional commit.
8. Do not push unless the user explicitly requested push.
9. Report the commit, tests/checks, changed-file count, and any deliberate follow-up.

## Stop conditions

Do not commit if:
- the work unit is incomplete;
- relevant tests/checks fail;
- the diff contains unrelated changes;
- the diff has crossed the repository's default scope threshold (10 files or 300 lines) without an explicit reason;
- or the acceptance criteria are not satisfied.

When a stop condition occurs, explain the blocker and remain on the current checkpoint.