#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent
PHASES_DIR = WORKROOM_DIR / "phases"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9가-힣]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "task"


def phase_id(number: int) -> str:
    return f"phase-{number:02d}"


def write_phase(task_dir: Path, number: int, title: str) -> None:
    pid = phase_id(number)
    path = task_dir / f"{pid}.md"
    path.write_text(
        f"""# {pid}: {title}

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

- Replace this list with concrete implementation tasks.
- Keep the phase small enough to verify independently.

## Acceptance Criteria

- The phase matches documented scope.
- The implementation follows architecture rules.
- `.workroom/scripts/verify.sh` passes.

## Verification

```bash
bash .workroom/scripts/verify.sh
```

## Status Update

When this phase cannot continue, update `.workroom/phases/{task_dir.name}/index.json`:

- user action needed: set this phase to `"status": "blocked"` and add `"blocked_reason"`
- truly unrecoverable implementation problem: set this phase to `"status": "error"` and add `"error_message"`

Do not mark this phase as completed yourself. Do not write `completed_at` or `summary`. The harness marks completion and writes the summary only after verification and review approval.
Do not mark this phase as blocked only because verification commands, dev-server commands, browser checks, or manual UI checks need approval or cannot run inside the worker session. Implement the phase, note skipped local checks in your final summary, and let the harness run verification and review.
If an API key, secret, account connection, deployment setting, or manual check is needed only after implementation, add it to this phase's `"deferred_requirements"` list in `index.json` instead of blocking.
""",
        encoding="utf-8",
    )


def update_top_index(task_name: str) -> None:
    PHASES_DIR.mkdir(exist_ok=True)
    path = PHASES_DIR / "index.json"
    if path.exists():
        index = json.loads(path.read_text(encoding="utf-8"))
    else:
        index = {"tasks": []}

    tasks = index.setdefault("tasks", [])
    if not any(task.get("dir") == task_name for task in tasks):
        tasks.append({"dir": task_name, "status": "planned"})

    path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold placeholder Workroom Harness phase files.")
    parser.add_argument("task", help="Task name, for example: add-youtube-url-input")
    parser.add_argument("--phases", type=int, default=1, help="Number of phase files to create")
    parser.add_argument(
        "--title",
        action="append",
        default=[],
        help="Phase title. Repeat for multiple phases.",
    )
    args = parser.parse_args()

    task_name = slugify(args.task)
    task_dir = WORKROOM_DIR / "phases" / task_name
    if task_dir.exists():
        print(f"ERROR: {task_dir.relative_to(ROOT)} already exists")
        return 1

    task_dir.mkdir(parents=True)

    phase_count = max(args.phases, len(args.title), 1)
    phases = []
    for number in range(1, phase_count + 1):
        title = args.title[number - 1] if number <= len(args.title) else f"Phase {number}"
        pid = phase_id(number)
        write_phase(task_dir, number, title)
        phases.append(
            {
                "id": pid,
                "title": title,
                "file": f"{pid}.md",
                "status": "pending",
            }
        )

    index = {
        "task": task_name,
        "status": "planned",
        "phases": phases,
    }
    (task_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    update_top_index(task_name)

    print(f"Created .workroom/phases/{task_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
