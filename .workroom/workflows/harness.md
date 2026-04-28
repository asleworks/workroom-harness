# Harness Workflow

Use this workflow to execute an existing phase plan from start to finish.

## Purpose

Run each phase through a controlled headless loop:

```text
fresh worker run implements phase
-> verification runs
-> fresh reviewer run reviews the phase
-> fresh worker run fixes review findings
-> reviewer approves
-> next phase starts
```

The main agent should not spend its context doing implementation work. It should start the harness script, then summarize the result.

## Inputs

Before running this workflow, `.workroom/workflows/phase.md` should have created:

```text
.workroom/phases/{task-name}/index.json
.workroom/phases/{task-name}/phase-01.md
.workroom/phases/{task-name}/phase-02.md
...
```

## Execution

In Codex, `$workroom-harness` should run:

```bash
python3 .workroom/scripts/run_phases.py --agent codex
```

When there is exactly one planned or running task in `.workroom/phases/index.json`, the script selects it automatically. When there are multiple runnable tasks, choose the task explicitly:

```bash
python3 .workroom/scripts/run_phases.py {task-name} --agent codex
```

The script is the harness engine. It is responsible for:

- writing a phase-local context snapshot at `.workroom/phases/{task-name}/context.md`
- sending each phase to a fresh headless worker run
- running `.workroom/scripts/verify.sh`
- sending the completed phase to a fresh headless reviewer run
- sending review findings back to the worker
- repeating until approval or retry limit
- updating phase status in `.workroom/phases/{task-name}/index.json`
- preserving each completed phase summary for the next worker and reviewer

Codex uses `codex exec`.

## Phase Completion Rule

A phase is complete only when all are true:

- worker implementation finished
- `.workroom/scripts/verify.sh` passed
- reviewer returned `REVIEW_DECISION: APPROVED`
- phase status was updated to `completed`

## Failure Handling

If verification or review fails repeatedly:

1. keep the logs in the phase directory
2. mark the phase as `error` or `blocked`
3. write the concrete reason in `index.json`
4. stop before starting the next phase

## Prohibited

- Do not skip review.
- Do not start the next phase before the current phase is approved.
- Do not mark a phase complete if verification fails.
- Do not weaken tests, types, or verification commands to pass the harness.
