#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent
ALLOWED_TASK_STATUSES = {"planned", "running", "completed", "error", "blocked"}
ALLOWED_PHASE_STATUSES = {"pending", "retrying", "completed", "error", "blocked"}
PLACEHOLDER_MARKERS = [
    "Describe the outcome this phase must produce.",
    "Replace this list with concrete implementation tasks.",
    "Replace with concrete file paths or directories.",
    "List the concrete implementation tasks.",
    "Describe the first phase",
    "Phase title",
]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_task(task_dir: Path) -> list[str]:
    errors: list[str] = []
    index_path = task_dir / "index.json"

    if not index_path.exists():
        return [f"missing {index_path.relative_to(ROOT)}"]

    try:
        index = read_json(index_path)
    except Exception as exc:
        return [f"invalid json {index_path.relative_to(ROOT)}: {exc}"]

    task = index.get("task")
    if not isinstance(task, str) or not task.strip():
        errors.append(f"{index_path.relative_to(ROOT)}: task must be a non-empty string")
    elif task != task_dir.name:
        errors.append(f"{index_path.relative_to(ROOT)}: task must match directory name {task_dir.name!r}")

    status = index.get("status", "planned")
    if status not in ALLOWED_TASK_STATUSES:
        errors.append(f"{index_path.relative_to(ROOT)}: invalid status {status!r}")

    phases = index.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append(f"{index_path.relative_to(ROOT)}: phases must be a non-empty list")
        return errors

    seen_ids = set()
    for number, phase in enumerate(phases, start=1):
        if not isinstance(phase, dict):
            errors.append(f"{index_path.relative_to(ROOT)}: phase {number} must be an object")
            continue

        phase_id = phase.get("id")
        title = phase.get("title")
        file_name = phase.get("file")
        phase_status = phase.get("status")
        expected_phase_id = f"phase-{number:02d}"
        expected_file_name = f"{expected_phase_id}.md"

        if not isinstance(phase_id, str) or not phase_id.strip():
            errors.append(f"{index_path.relative_to(ROOT)}: phase {number} id must be a non-empty string")
        elif phase_id in seen_ids:
            errors.append(f"{index_path.relative_to(ROOT)}: duplicate phase id {phase_id!r}")
        elif phase_id != expected_phase_id:
            errors.append(f"{index_path.relative_to(ROOT)}: phase {number} id should be {expected_phase_id!r}")
        else:
            seen_ids.add(phase_id)

        if not isinstance(title, str) or not title.strip():
            errors.append(f"{index_path.relative_to(ROOT)}: phase {phase_id or number} title must be a non-empty string")

        if phase_status not in ALLOWED_PHASE_STATUSES:
            errors.append(f"{index_path.relative_to(ROOT)}: phase {phase_id or number} invalid status {phase_status!r}")

        if not isinstance(file_name, str) or not file_name.endswith(".md"):
            errors.append(f"{index_path.relative_to(ROOT)}: phase {phase_id or number} file must be a markdown file")
            continue
        if file_name != expected_file_name:
            errors.append(f"{index_path.relative_to(ROOT)}: phase {phase_id or number} file should be {expected_file_name!r}")

        phase_path = task_dir / file_name
        if not phase_path.exists():
            errors.append(f"missing {phase_path.relative_to(ROOT)}")
            continue

        text = phase_path.read_text(encoding="utf-8")
        for heading in [
            "## Goal",
            "## Read",
            "## Likely Files To Modify",
            "## Work",
            "## Acceptance Criteria",
            "## Verification",
            "## Status Update",
        ]:
            if heading not in text:
                errors.append(f"{phase_path.relative_to(ROOT)}: missing {heading}")

        for marker in PLACEHOLDER_MARKERS:
            if marker in text:
                errors.append(f"{phase_path.relative_to(ROOT)}: placeholder remains: {marker}")

        if ".workroom/scripts/verify.sh" not in text:
            errors.append(f"{phase_path.relative_to(ROOT)}: missing verification command .workroom/scripts/verify.sh")

    return errors


def validate_top_index(task_dir: Path) -> list[str]:
    top_index_path = WORKROOM_DIR / "phases/index.json"

    if not top_index_path.exists():
        return [f"missing {top_index_path.relative_to(ROOT)}"]

    try:
        index = read_json(top_index_path)
    except Exception as exc:
        return [f"invalid json {top_index_path.relative_to(ROOT)}: {exc}"]

    tasks = index.get("tasks")
    if not isinstance(tasks, list):
        return [f"{top_index_path.relative_to(ROOT)}: tasks must be a list"]

    for task in tasks:
        if not isinstance(task, dict):
            continue
        if task.get("dir") == task_dir.name:
            status = task.get("status", "planned")
            if status not in ALLOWED_TASK_STATUSES:
                return [f"{top_index_path.relative_to(ROOT)}: task {task_dir.name!r} has invalid status {status!r}"]
            return []

    return [f"{top_index_path.relative_to(ROOT)}: missing task entry for {task_dir.name!r}"]


def discover_tasks() -> list[Path]:
    phases_dir = WORKROOM_DIR / "phases"
    if not phases_dir.exists():
        return []
    return sorted(path for path in phases_dir.iterdir() if path.is_dir() and (path / "index.json").exists())


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Workroom Harness phase plans.")
    parser.add_argument("task", nargs="?", help="Task directory under .workroom/phases/. If omitted, validate all tasks.")
    args = parser.parse_args()

    if args.task:
        task_dirs = [WORKROOM_DIR / "phases" / args.task.strip().strip("/")]
    else:
        task_dirs = discover_tasks()

    if not task_dirs:
        print("No phase tasks found.")
        return 0

    errors = []
    for task_dir in task_dirs:
        errors.extend(validate_task(task_dir))
        errors.extend(validate_top_index(task_dir))

    if errors:
        for error in errors:
            print(f"FAIL  {error}")
        return 1

    for task_dir in task_dirs:
        print(f"OK    {task_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
