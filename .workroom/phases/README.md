# Phases

This directory is intentionally empty in the template.

AI agents create task-specific phase plans here when they follow `.workroom/workflows/phase.md`.

Each task should have its own directory:

```text
.workroom/phases/
└── add-search/
    ├── index.json
    ├── phase-01.md
    └── phase-02.md
```

Keep phases small enough to verify independently.

Run created phases with:

```bash
python3 .workroom/scripts/run_phases.py --agent codex
python3 .workroom/scripts/run_phases.py --agent claude
```

If multiple planned or running tasks exist, pass `{task-name}` explicitly.

During execution, the harness writes:

```text
.workroom/phases/{task-name}/context.md
```

This is a snapshot of `.workroom/AGENTS.md`, `.workroom/workflows/`, and `.workroom/docs/` for worker and reviewer agents.

Reusable file shapes live under `.workroom/templates/`.
