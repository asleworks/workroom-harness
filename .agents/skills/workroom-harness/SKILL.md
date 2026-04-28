---
name: workroom-harness
description: Execute an existing Workroom Harness phase plan from start to finish. Use when the user invokes $workroom-harness after phases have been created. Runs worker, verification, reviewer, fix, and approval loops.
---

You are the Workroom Harness orchestrator.

Follow `.workroom/workflows/harness.md`.

Required behavior:

1. Run `python3 .workroom/scripts/run_phases.py --agent codex`.
2. If the script reports multiple runnable tasks, ask the user which task to run, then run `python3 .workroom/scripts/run_phases.py {task-name} --agent codex`.
3. If the script reports no runnable task, tell the user to run `$workroom-phase` first.
4. Do not manually implement phases in the main conversation.
5. Use `python3 .workroom/scripts/workroom_status.py` to inspect current state when the runner is still active, quiet, paused, or complete. A retryable pause can exit `0`; do not report completion unless the script reports `Completed .workroom/phases/{task-name}` or the status command shows `completed` / `completed_with_deferred_requirements`.

The harness loop is:

```text
codex exec worker
-> verify.sh
-> codex exec reviewer
-> codex exec fix
-> reviewer approval
-> next phase
```

Stop and report if the harness pauses with a phase left `pending` and a `last_failure_reason`, or if the status command shows a real user-facing `error` or `blocked` state.
