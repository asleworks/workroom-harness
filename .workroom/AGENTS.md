# .workroom/AGENTS.md

This is the common operating guide for Codex coding agents.

The defaults below are intentionally conservative. They work for most software projects. Customize the project profile, stack, architecture boundaries, and verification commands for your repository.

## Project Profile

- Project name: Workroom Harness Project
- Product goal: Build a small, scoped, verifiable software project with AI assistance.
- Primary users: project maintainers and AI coding agents
- Current stage: prototype or MVP

## Stack

- Language: define in `.workroom/docs/ARCHITECTURE.md`
- Framework: define in `.workroom/docs/ARCHITECTURE.md`
- Package manager: define in `.workroom/docs/ARCHITECTURE.md`
- Test runner: define in `.workroom/docs/TEST_STRATEGY.md`
- Build command: define in `.workroom/scripts/verify.sh`
- Deploy target: none unless explicitly documented

## Project Rules

Agents must follow these rules:

- Do not expand scope beyond `.workroom/docs/PRD.md`.
- Preserve the architecture described in `.workroom/docs/ARCHITECTURE.md`.
- Follow decisions recorded in `.workroom/docs/ADR.md`.
- Do not add dependencies without explaining why.
- Do not mark work complete until verification passes.
- Do not delete or weaken tests to make checks pass.

Project-specific rules should be added here when they become important enough to enforce repeatedly.

## Decision Boundaries

Agents may decide:

- Small implementation details that do not change documented product behavior.
- Local refactors needed to satisfy the current phase.
- Test organization when it follows `.workroom/docs/TEST_STRATEGY.md`.

Agents must ask before deciding:

- Expanding MVP scope.
- Adding authentication, payment, persistence, deployment, or background jobs.
- Introducing new dependencies or external services.
- Changing architecture boundaries or ADR decisions.

## Architecture Boundaries

- UI code must not call external APIs directly.
- Database access must go through the data access layer.
- Shared types must live in the agreed type directory.
- Feature code must not modify deployment configuration.
- Do not introduce new top-level directories without updating `.workroom/docs/ARCHITECTURE.md`.

## Verification

Before marking implementation work complete, run:

```bash
.workroom/scripts/verify.sh
```

Make sure `.workroom/scripts/verify.sh` contains the real checks for your project.

Expected checks:

- lint
- typecheck
- test
- build

If a check cannot run locally, explain why in the final response and mark the related phase as `blocked` when appropriate.

## Harness Workflow

For project doc planning:

```text
.workroom/workflows/plan.md
```

For phase planning:

```text
.workroom/workflows/phase.md
```

For full phase execution:

```text
.workroom/workflows/harness.md
```

For review work:

```text
.workroom/workflows/review.md
```

For verification failures:

```text
.workroom/workflows/fix.md
```

To create phase files manually:

```bash
python3 .workroom/scripts/scaffold_phases.py task-name --title "Phase title"
```

After replacing placeholders with concrete phase instructions:

```bash
python3 .workroom/scripts/validate_phases.py task-name
```

To execute phase files:

```bash
python3 .workroom/scripts/run_phases.py --agent codex
python3 .workroom/scripts/run_phases.py --agent claude
```

If multiple planned or running tasks exist, pass the task name explicitly:

```bash
python3 .workroom/scripts/run_phases.py task-name --agent codex
python3 .workroom/scripts/run_phases.py task-name --agent claude
```

Preferred skill entrypoints:

- Codex: `$workroom-plan`, then `$workroom-phase`, then `$workroom-harness`
- Claude: `/workroom-plan`, then `/workroom-phase`, then `/workroom-harness`

Plan and phase review gates use fresh read-only review agents through `.workroom/scripts/review_artifacts.py`.

Harness execution uses fresh headless agent runs through `.workroom/scripts/run_phases.py`:

- Codex runner: `codex exec`
- Claude runner: `claude -p`

Each stage has a review gate:

- `workroom-plan`: fresh docs review agent and `.workroom/scripts/validate_docs.py`
- `workroom-phase`: fresh phase-plan review agent and `.workroom/scripts/validate_phases.py`
- `workroom-harness`: implementation review inside `.workroom/scripts/run_phases.py`

## Phase Status Rules

When working inside `.workroom/phases/{task-name}/`, update `index.json`:

- `completed`: phase finished, verification passed, and reviewer approved
- `completed_with_deferred_requirements`: task finished, with user-provided values or manual checks remaining after implementation
- `running`: harness has started a worker run
- `reviewing`: harness has started a read-only reviewer run
- `retrying`: harness will rerun the worker with verification or review feedback
- `error`: worker explicitly determined that the phase is unrecoverable
- `blocked`: user action or external setup is required

Only the harness should mark a phase as `completed`. Worker agents may mark `error` or `blocked` when they cannot continue because of a real user/external dependency, but the harness treats those states as feedback first and retries while progress is possible.

Do not mark a phase `blocked` only because verification commands, dev-server commands, browser checks, or manual UI checks need approval or cannot run inside a worker session. Those are harness verification/review concerns, not user blockers. Implement the phase, note skipped local checks in the phase summary, and let the harness continue.

If an API key, secret, account connection, deployment setting, or manual check is needed only after implementation, record it in `deferred_requirements` instead of blocking. The harness should finish the implementation and report deferred requirements at the end.

Every completed phase should include a short `summary` that the next worker and reviewer can read.

Verification or review failures are worker feedback by default. The harness should keep fixing while the failure or repository diff is changing, and pause only when attempts stall on the same failure and same repository state or hit the safety budget. On pause, leave the phase `pending`, record `last_failure_reason` and `last_failure_log`, and feed that failure back into the next worker prompt instead of locking the phase as `error`.

## Forbidden Actions

Do not run or perform these unless the user explicitly asks and the risk is clear:

- `rm -rf`
- `git reset --hard`
- `git push --force`
- `DROP TABLE`
- deleting migration history
- deleting tests to pass verification
- weakening type checks to hide an error

Add project-specific forbidden actions:

- changing production deployment settings without explicit approval
- adding secrets, API keys, or tokens to the repository

## Review Expectations

When reviewing work, check:

- PRD scope
- architecture rules
- ADR consistency
- tests and verification
- error handling
- type safety
- unnecessary dependencies
- security-sensitive changes
