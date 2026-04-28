# Fix Workflow

Use this workflow when verification, review, or a phase run reports a concrete failure.

## Procedure

1. Read the latest error log, review finding, or verification output.
2. Classify the failure.
3. Identify the root cause.
4. Fix the root cause with the smallest reasonable change.
5. Run verification again.
6. Summarize the fix and any remaining risk.

## Rules

- Do not hide errors.
- Do not delete tests to make verification pass.
- Do not replace useful types with `any`.
- Do not weaken verification commands.
- Do not expand scope while fixing a failure.
- If user intervention is required, mark the phase as `blocked` with a concrete reason.
