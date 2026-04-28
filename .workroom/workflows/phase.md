# Phase Workflow

Use this workflow to turn project context and a user request into executable phase files.

## Purpose

Do not implement. Read the approved project docs, identify missing decisions, create a phase plan, review the phase plan, improve it, and stop only when the phase plan is executable.

## 1. Load Context

Read:

- `.workroom/AGENTS.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`

## 2. Check Readiness

Review whether the docs are detailed enough to implement the requested work.

Look for:

- unclear product behavior
- missing MVP boundaries
- missing architecture boundaries
- missing test expectations
- external APIs, credentials, or user actions that cannot be completed locally

If missing decisions would change the implementation, stop and send the user back to `workroom-plan`.

If the user invoked this workflow without a concrete implementation request, ask one question:

```text
What implementation task should I break into phases?
```

Run:

```bash
python3 .workroom/scripts/validate_docs.py
```

Fix only obvious documentation formatting issues. If product decisions are missing, stop and report the missing decisions.

## 3. Create Phase Plan

Create:

```text
.workroom/phases/{task-name}/index.json
.workroom/phases/{task-name}/phase-01.md
.workroom/phases/{task-name}/phase-02.md
...
```

Also update:

```text
.workroom/phases/index.json
```

Phase ids and file names must be sequential and must match the task index:

```text
phase-01 -> phase-01.md
phase-02 -> phase-02.md
phase-03 -> phase-03.md
```

Create phase files directly when possible. Use `.workroom/scripts/scaffold_phases.py` only as a manual fallback, then replace all placeholder content with concrete instructions.

After creating phase files, run:

```bash
python3 .workroom/scripts/validate_phases.py {task-name}
```

Fix validation failures before running `workroom-harness`.

## 4. Phase Review Gate

Run a fresh read-only review agent:

```bash
python3 .workroom/scripts/review_artifacts.py phases {task-name} --agent auto
```

The review agent uses `.workroom/workflows/review.md` in `phases` mode and returns structured JSON validated by `.workroom/schemas/review-result.schema.json`.

Check:

- phases are small enough for fresh headless worker runs
- every phase has concrete work and acceptance criteria
- phase order is dependency-safe
- phase ids and file names are sequential
- `.workroom/phases/index.json` includes the task
- likely files to modify are concrete paths or directories
- docs updates happen before implementation when needed
- test/verification expectations are clear
- required checks are automatable through `.workroom/scripts/verify.sh` or reviewable from code; manual UI/dev-server checks may be optional notes but must not be the only blocking completion condition unless the user explicitly requested manual approval
- post-implementation API keys, account connections, deployment settings, or manual checks are planned as `deferred_requirements`, not mid-run blockers
- no phase contains vague manual judgment as its only completion condition
- no placeholder text remains

The review script exits `0` for any valid review decision. Inspect the JSON decision, not only the shell exit code.

If the review JSON contains `"decision": "CHANGES_REQUESTED"`, improve the phase files using the concrete review fields and run the review agent again.

Do not continue to harness execution until the fresh review JSON contains `"decision": "APPROVED"`.

After the fresh phase-plan review agent approves, run validation again:

```bash
python3 .workroom/scripts/validate_phases.py {task-name}
```

## 5. Phase Requirements

Each phase file must be self-contained and include:

- goal
- files to read
- likely files to modify
- implementation steps
- acceptance criteria
- verification commands
- status update instructions

Write each phase for a fresh worker agent that does not share the planner's conversation history.

The harness runtime will create `.workroom/phases/{task-name}/context.md` before execution. Phase files should still list any special files they need beyond the shared context snapshot.

## 6. Planning Rules

- Keep phases small enough to verify independently.
- Prefer 3-8 phases for a normal MVP-sized feature. Use more only when dependencies require it.
- Each phase should leave the project in a verifiable state.
- Put docs updates before implementation when the task changes product or architecture decisions.
- Avoid phases that require vague manual judgment.
- Do not create demo/example phases unless the user asked for them.
- Do not implement code while planning.
