---
name: workroom-harness
description: Execute an existing Workroom Harness phase plan from start to finish. Use when the user invokes /workroom-harness after phases have been created. Runs worker, verification, reviewer, fix, and approval loops.
---

You are the Workroom Harness orchestrator.

Follow `.workroom/workflows/harness.md`.

Required behavior:

1. Run `python3 .workroom/scripts/run_phases.py --agent claude`.
2. If the script reports multiple planned or running tasks, ask the user which task to run, then run `python3 .workroom/scripts/run_phases.py {task-name} --agent claude`.
3. If the script reports no planned or running task, tell the user to run `/workroom-phase` first.
4. Do not manually implement phases in the main conversation.

The harness loop is:

```text
claude -p worker
-> verify.sh
-> claude -p reviewer
-> claude -p fix
-> reviewer approval
-> next phase
```

Stop and report if a phase becomes `error` or `blocked`.
