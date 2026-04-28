# Phase 01: Phase Title

## Goal

Describe the outcome this phase must produce.

## Read

- `.workroom/AGENTS.md`
- `.workroom/workflows/harness.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`

## Likely Files To Modify

- Replace with concrete file paths or directories.

## Work

- List the concrete implementation tasks.
- Keep this phase small enough to verify independently.

## Acceptance Criteria

- The phase matches documented scope.
- The implementation follows architecture rules.
- `.workroom/scripts/verify.sh` passes.
- The review agent returns `REVIEW_DECISION: APPROVED`.

## Verification

```bash
.workroom/scripts/verify.sh
```

## Status Update

Do not mark this phase as completed manually. The harness marks completion only after verification and review approval.

If the phase cannot continue, update `index.json` with either:

- `"status": "blocked"` and `"blocked_reason"`
- `"status": "error"` and `"error_message"`
