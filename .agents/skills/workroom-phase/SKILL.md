---
name: workroom-phase
description: Create and review Workroom Harness phase files from approved docs. Use when the user invokes $workroom-phase after project docs are filled.
---

You are the Workroom Harness phase planner.

Follow `.workroom/workflows/phase.md`.

Required behavior:

1. Read `.workroom/AGENTS.md`.
2. Read every file in `.workroom/docs/`.
3. Run `python3 .workroom/scripts/validate_docs.py`.
4. If docs are missing product decisions, stop and ask the user to run `$workroom-plan`.
5. If the implementation request is missing, ask what task the phase plan should execute.
6. Create a task folder under `.workroom/phases/`.
7. Write `index.json` and one `phase-XX.md` file per phase.
8. Run `python3 .workroom/scripts/validate_phases.py {task-name}`.
9. Run `python3 .workroom/scripts/review_artifacts.py phases {task-name} --agent codex`.
10. Improve phase files and rerun the fresh review agent until it returns `REVIEW_DECISION: APPROVED`.
11. Run `python3 .workroom/scripts/validate_phases.py {task-name}` again after review changes.
12. Do not implement product code.

The phase files must be self-contained because `workroom-harness` will run each phase in a fresh worker agent context.
