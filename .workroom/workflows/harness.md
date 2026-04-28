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

In Claude Code, `/workroom-harness` should run:

```bash
python3 .workroom/scripts/run_phases.py --agent claude
```

When there is exactly one planned or running task in `.workroom/phases/index.json`, the script selects it automatically. When there are multiple runnable tasks, choose the task explicitly:

```bash
python3 .workroom/scripts/run_phases.py {task-name} --agent codex
python3 .workroom/scripts/run_phases.py {task-name} --agent claude
```

The script is the harness engine. It is responsible for:

- writing a phase-local context snapshot at `.workroom/phases/{task-name}/context.md`
- sending each phase to a fresh headless worker run
- running `.workroom/scripts/verify.sh`
- sending the completed phase to a fresh headless reviewer run
- sending review findings back to the worker
- repeating until approval, no-progress stall, or the safety budget
- updating phase status in `.workroom/phases/{task-name}/index.json`
- preserving each completed phase summary for the next worker and reviewer

Codex uses `codex exec`. Claude Code uses `claude -p`.

Runner safeguards:

- Agent output is streamed into the phase log while the process is running.
- Prompt input is passed through a temporary stdin file instead of an in-memory pipe write.
- Routine verification or review failures are treated as internal fix-loop feedback. The default CLI output stays concise and points to logs; use `--verbose` to print full failure output on each attempt.
- `WORKROOM_PHASE_MAX_ATTEMPTS` controls the per-phase safety budget. Default: `50`.
- `WORKROOM_PHASE_MAX_RETRIES` is kept as a backward-compatible alias when `WORKROOM_PHASE_MAX_ATTEMPTS` is not set.
- `WORKROOM_PHASE_STALL_LIMIT` controls how many consecutive attempts may repeat the same failure and repository state before the harness pauses. Default: `5`.
- `WORKROOM_AGENT_TOTAL_TIMEOUT_SECONDS` controls the wall-clock runner timeout. Default: `7200`.
- `WORKROOM_AGENT_IDLE_TIMEOUT_SECONDS` is disabled by default. Set it only when a project explicitly wants no-output watchdog behavior.

## Phase Completion Rule

A phase is complete only when all are true:

- worker implementation finished
- `.workroom/scripts/verify.sh` passed
- reviewer returned structured JSON with `"decision": "APPROVED"`
- harness updated the phase with `status`, `completed_at`, and `summary`

## Failure Handling

If verification or review fails without the worker explicitly marking the phase blocked or unrecoverable:

1. keep the logs in the phase directory
2. feed the concrete verification/review failure and current repository diff back to the next fix worker
3. record `last_failed_at` and `last_failure_reason` after each failed attempt
4. keep running while the failure or repository diff is changing, because that means the workers are still making progress
5. pause only after the same failure and same repository state repeat for `WORKROOM_PHASE_STALL_LIMIT` attempts, or after the safety budget is exhausted
6. leave the phase `pending`
7. record `last_failure_attempts`, `last_stalled_attempts`, and `last_failure_log`
8. include the previous failure in the next worker prompt when the harness is rerun
9. stop before starting the next phase so the harness can be rerun after fixes or prompt updates

This retryable pause is not a CLI error by default. The script exits `0` so agent shells do not treat normal harness pauses as command failures. Use `--strict-exit-codes` only in CI or external automation that needs a non-zero exit for incomplete runs.

If the worker explicitly determines that user action is required or the phase is unrecoverable:

1. mark the phase as `blocked` or `error`
2. write the concrete reason in `index.json`
3. stop before starting the next phase

If the agent runner itself fails before verification or review can complete:

1. leave the phase runnable
2. record `last_runner_error` and `last_runner_log`
3. stop so the operator can fix the runner environment and retry

## Prohibited

- Do not skip review.
- Do not start the next phase before the current phase is approved.
- Do not mark a phase complete if verification fails.
- Worker and reviewer agents must not require or write `status: completed`, `completed_at`, or `summary`; those fields are harness-owned and are written only after approval.
- Do not weaken tests, types, or verification commands to pass the harness.
