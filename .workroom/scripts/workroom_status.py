#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_tasks() -> list[str]:
    phases_dir = WORKROOM_DIR / "phases"
    if not phases_dir.exists():
        return []
    tasks = []
    for path in sorted(phases_dir.iterdir()):
        if path.is_dir() and (path / "index.json").exists():
            tasks.append(path.name)
    return tasks


def top_index_tasks() -> list[str]:
    path = WORKROOM_DIR / "phases/index.json"
    if not path.exists():
        return []
    try:
        index = read_json(path)
    except Exception:
        return []
    tasks = index.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    return [str(task.get("dir", "")).strip() for task in tasks if isinstance(task, dict) and str(task.get("dir", "")).strip()]


def resolve_task(requested: str | None) -> str | None:
    if requested:
        return requested.strip().strip("/")
    tasks = top_index_tasks() or discover_tasks()
    runnable = []
    top_path = WORKROOM_DIR / "phases/index.json"
    if top_path.exists():
        try:
            top = read_json(top_path)
            for task in top.get("tasks", []):
                if isinstance(task, dict) and task.get("status", "planned") in {"planned", "running", "blocked", "error"} and task.get("dir"):
                    runnable.append(str(task["dir"]))
        except Exception:
            pass
    if len(runnable) == 1:
        return runnable[0]
    if len(tasks) == 1:
        return tasks[0]
    return None


def current_phase(index: dict) -> dict | None:
    for phase in index.get("phases", []):
        if isinstance(phase, dict) and phase.get("status") != "completed":
            return phase
    return None


def print_status(task_name: str) -> int:
    task_dir = WORKROOM_DIR / "phases" / task_name
    index_path = task_dir / "index.json"
    status_path = task_dir / "status.json"
    if not index_path.exists():
        print(f"ERROR: phase task not found: .workroom/phases/{task_name}")
        return 1

    index = read_json(index_path)
    status = read_json(status_path) if status_path.exists() else {}
    phase = current_phase(index)
    phases = [item for item in index.get("phases", []) if isinstance(item, dict)]
    completed = sum(1 for item in phases if item.get("status") == "completed")

    print(f"Task: {task_name}")
    print(f"Task status: {index.get('status', 'unknown')}")
    if status:
        print(f"Stage: {status.get('stage', 'unknown')}")
        print(f"Last event: {status.get('event', 'unknown')}")
        print(f"Updated: {status.get('updated_at', 'unknown')}")
        if status.get("pid"):
            print(f"Runner PID: {status['pid']}")
        if status.get("log"):
            print(f"Current log: {status['log']}")
    else:
        print("Stage: not running or no status.json yet")

    print(f"Progress: {completed}/{len(phases)} phases completed")
    if phase:
        print(f"Current phase: {phase.get('id', 'unknown')} - {phase.get('title', '')}")
        print(f"Current phase status: {phase.get('status', 'pending')}")
        if phase.get("last_failure_reason"):
            print(f"Last failure: {phase['last_failure_reason']}")
        if phase.get("last_failure_log"):
            print(f"Last failure log: {phase['last_failure_log']}")
    else:
        print("Current phase: none")

    deferred = index.get("deferred_requirements") or status.get("deferred_requirements")
    if deferred:
        print("Deferred requirements:")
        for item in deferred:
            print(f"- {item}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the current Workroom Harness task status.")
    parser.add_argument("task", nargs="?", help="Task directory under .workroom/phases/.")
    args = parser.parse_args()

    task_name = resolve_task(args.task)
    if not task_name:
        tasks = top_index_tasks() or discover_tasks()
        if not tasks:
            print("No phase tasks found.")
            return 0
        print("ERROR: Could not choose a task automatically. Pass a task name.")
        for task in tasks:
            print(f"- {task}")
        return 1
    return print_status(task_name)


if __name__ == "__main__":
    raise SystemExit(main())
