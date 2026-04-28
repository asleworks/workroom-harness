#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_runner import check_agent, is_agent_infrastructure_failure, parse_review_result, resolve_agent, run_agent as run_agent_process
from validate_phases import validate_task, validate_top_index


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent
REVIEW_SCHEMA = WORKROOM_DIR / "schemas/review-result.schema.json"
MAX_RETRIES = 3
RUNNABLE_PHASE_STATUSES = {"pending", "running", "reviewing", "retrying"}
STOP_PHASE_STATUSES = {"blocked", "error"}


def stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_context() -> str:
    parts = []
    for path in [
        WORKROOM_DIR / "AGENTS.md",
        WORKROOM_DIR / "workflows/harness.md",
        WORKROOM_DIR / "workflows/fix.md",
        WORKROOM_DIR / "workflows/review.md",
        WORKROOM_DIR / "docs/PRD.md",
        WORKROOM_DIR / "docs/ARCHITECTURE.md",
        WORKROOM_DIR / "docs/ADR.md",
        WORKROOM_DIR / "docs/TEST_STRATEGY.md",
    ]:
        if path.exists():
            parts.append(f"# {path.relative_to(ROOT)}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(parts)


def write_context_snapshot(task_dir: Path) -> Path:
    path = task_dir / "context.md"
    path.write_text(load_context(), encoding="utf-8")
    return path


def run(
    command: list[str],
    log_path: Path | None = None,
    input_text: str | None = None,
    cwd: Path = ROOT,
) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, input=input_text)
    output = result.stdout + result.stderr
    if log_path:
        log_path.write_text(output, encoding="utf-8")
    return result.returncode, output


def run_agent(
    agent: str,
    prompt: str,
    log_path: Path,
    read_only: bool = False,
    output_schema: Path | None = None,
) -> tuple[int, str]:
    return run_agent_process(agent, ROOT, prompt, log_path, read_only=read_only, output_schema=output_schema)


def summarize_runner_error(output: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("ERROR:") or "Fatal error:" in stripped:
            return stripped
    return "Agent runner failed before the phase could be approved."


def abort_agent_infrastructure_failure(
    agent: str,
    output: str,
    log_path: Path,
    index_path: Path,
    phase_id: str,
) -> int:
    set_phase_status(
        index_path,
        phase_id,
        "pending",
        last_runner_failed_at=stamp(),
        last_runner_error=summarize_runner_error(output),
        last_runner_log=str(log_path.relative_to(ROOT)),
    )
    print(f"ERROR: {agent} runner failed before the phase could run.")
    print("The harness is leaving the phase runnable. Fix the runner permission issue and rerun workroom-harness.")
    print(f"Log: {log_path.relative_to(ROOT)}")
    if output.strip():
        print()
        print(output.strip())
    return 1


def set_phase_status(index_path: Path, phase_id: str, status: str, **fields: str | int) -> None:
    index = read_json(index_path)
    for item in index.get("phases", []):
        if item.get("id") == phase_id:
            item["status"] = status
            item[f"{status}_at"] = stamp()
            item.update(fields)
            break
    write_json(index_path, index)


def update_top_index(task_name: str, status: str) -> None:
    path = WORKROOM_DIR / "phases/index.json"
    if not path.exists():
        return
    index = read_json(path)
    for task in index.get("tasks", []):
        if task.get("dir") == task_name:
            task["status"] = status
            task[f"{status}_at"] = stamp()
            break
    write_json(path, index)


def planned_tasks() -> list[dict]:
    path = WORKROOM_DIR / "phases/index.json"
    if not path.exists():
        return []

    index = read_json(path)
    tasks = index.get("tasks", [])
    if not isinstance(tasks, list):
        return []

    runnable_statuses = {"planned", "running"}
    return [
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("status", "planned") in runnable_statuses
        and isinstance(task.get("dir"), str)
        and task.get("dir")
    ]


def resolve_task_name(requested_task: str | None) -> str | None:
    if requested_task:
        return requested_task.strip().strip("/")

    tasks = planned_tasks()
    if len(tasks) == 1:
        return tasks[0]["dir"].strip().strip("/")

    if not tasks:
        print("ERROR: No planned or running phase task found.")
        print("Create phases first with workroom-phase.")
        return None

    print("ERROR: Multiple planned or running phase tasks found. Choose one:")
    for task in tasks:
        print(f"- {task['dir']} ({task.get('status', 'planned')})")
    return None


def phase_status(index_path: Path, phase_id: str) -> str:
    index = read_json(index_path)
    for phase in index.get("phases", []):
        if phase.get("id") == phase_id:
            return str(phase.get("status", "pending"))
    return "missing"


def extract_phase_summary(output: str, fallback: str) -> str:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("PHASE_SUMMARY:"):
            summary = line.removeprefix("PHASE_SUMMARY:").strip()
            if summary:
                return summary[:500]
    return fallback


def current_change_snapshot() -> str:
    sections: list[str] = []
    for title, command in [
        ("git status --short", ["git", "status", "--short"]),
        ("git diff --stat", ["git", "diff", "--stat"]),
        ("git diff", ["git", "diff", "--"]),
    ]:
        code, output = run(command)
        if code == 0 and output.strip():
            sections.append(f"## {title}\n\n```text\n{output[:50000]}\n```")
        elif code != 0:
            sections.append(f"## {title}\n\n```text\n{output[:5000]}\n```")
    return "\n\n".join(sections) or "No repository changes detected by git."


def review_feedback(result: dict) -> str:
    lines = [
        "Review requested changes.",
        "",
        f"Summary: {result.get('summary', '').strip()}",
    ]
    for key, title in [
        ("blocking_issues", "Blocking Issues"),
        ("missing_tests", "Missing Tests"),
        ("architecture_violations", "Architecture Violations"),
        ("recommended_fixes", "Recommended Fixes"),
    ]:
        items = [str(item).strip() for item in result.get(key, []) if str(item).strip()]
        if items:
            lines.append("")
            lines.append(f"{title}:")
            lines.extend(f"- {item}" for item in items)
    return "\n".join(lines).strip()


def phase_prompt(
    context_path: Path | None,
    task_name: str,
    phase_file: Path,
    previous_summaries: list[str],
) -> str:
    summaries = "\n".join(f"- {item}" for item in previous_summaries) or "- None"
    phase_ref = phase_file.relative_to(ROOT)
    if context_path:
        context_section = f"""## Required Reads

- `{context_path.relative_to(ROOT)}`
- `{phase_ref}`"""
    else:
        context_section = f"""## Required Reads

- `{phase_ref}`

## Context Snapshot

{load_context()}"""

    return f"""You are running one Workroom Harness phase.

Complete only the phase below.

{context_section}

## Previous Phase Summaries

{summaries}

## Required Output

After implementation, update `.workroom/phases/{task_name}/index.json` for this phase only if blocked or unrecoverable:

- repeated failure: `"status": "error"` and `"error_message"`
- user action needed: `"status": "blocked"` and `"blocked_reason"`

Do not write `"status": "completed"`, `"completed_at"`, or `"summary"` for this phase. The harness writes those fields only after verification and review approval, using the `PHASE_SUMMARY` line from your final response.

End your final response with one concise line:

```text
PHASE_SUMMARY: what changed and what the next phase should know
```

## Phase

{phase_file.read_text(encoding='utf-8')}
"""


def fix_prompt(
    context_path: Path,
    task_name: str,
    phase_file: Path,
    previous_summaries: list[str],
    feedback: str,
) -> str:
    summaries = "\n".join(f"- {item}" for item in previous_summaries) or "- None"
    context_ref = context_path.relative_to(ROOT)
    phase_ref = phase_file.relative_to(ROOT)
    return f"""You are fixing one Workroom Harness phase.

Use the context snapshot, previous phase summaries, current phase instructions, and feedback below.

Make the smallest reasonable change that resolves the feedback. Do not expand scope.

## Required Reads

- `{context_ref}`
- `{phase_ref}`

## Previous Phase Summaries

{summaries}

## Current Phase

{phase_file.read_text(encoding='utf-8')}

## Feedback To Fix

{feedback}

## Required Output

After fixing, update `.workroom/phases/{task_name}/index.json` for this phase only if the feedback requires a status change:

- user action needed: `"status": "blocked"` and `"blocked_reason"`
- unrecoverable repeated failure: `"status": "error"` and `"error_message"`

Do not write `"status": "completed"`, `"completed_at"`, or `"summary"` for this phase. The harness writes those fields only after verification and review approval, using the `PHASE_SUMMARY` line from your final response.

End your final response with one concise line:

```text
PHASE_SUMMARY: what changed and what the next phase should know
```
"""


def review_prompt(
    context_path: Path,
    task_name: str,
    phase_file: Path,
    verify_output: str,
    previous_summaries: list[str],
    change_snapshot: str,
) -> str:
    summaries = "\n".join(f"- {item}" for item in previous_summaries) or "- None"
    context_ref = context_path.relative_to(ROOT)
    phase_ref = phase_file.relative_to(ROOT)
    return f"""You are the Workroom Harness review agent.

Review the completed phase in read-only mode. Do not edit files.

You must decide whether this phase can be approved before the harness starts the next phase.

Inspect the current repository diff, changed files, verification output, phase acceptance criteria, and Workroom docs before deciding.

Harness-owned phase index fields are not worker deliverables. Do not request changes only because the current phase lacks `"status": "completed"`, `"completed_at"`, or `"summary"` in `.workroom/phases/{task_name}/index.json`; those fields are written by the harness only after reviewer approval.

## Required Reads

- `{context_ref}`
- `{phase_ref}`

## Previous Phase Summaries

{summaries}

## Phase To Review

{phase_file.read_text(encoding='utf-8')}

## Verification Output

{verify_output}

## Repository Change Snapshot

{change_snapshot}

## Required Review Output

Follow `.workroom/workflows/review.md`.

Return only the structured JSON object required by `.workroom/schemas/review-result.schema.json`.

Use `"decision": "APPROVED"` only if there are no blocking issues and the phase satisfies its acceptance criteria.
Use `"decision": "CHANGES_REQUESTED"` if the worker must change anything before the next phase.
"""


def first_runnable_phase(index: dict) -> tuple[dict, list[str]] | tuple[None, list[str]]:
    previous_summaries: list[str] = []
    for phase in index.get("phases", []):
        if phase.get("status") == "completed":
            if phase.get("summary"):
                previous_summaries.append(f"{phase['id']}: {phase['summary']}")
            continue
        return phase, previous_summaries
    return None, previous_summaries


def phase_can_start(phase: dict) -> tuple[bool, str]:
    status = str(phase.get("status", "pending"))
    phase_id = phase.get("id", "unknown")
    if status in RUNNABLE_PHASE_STATUSES:
        return True, ""
    if status in STOP_PHASE_STATUSES:
        detail_key = "blocked_reason" if status == "blocked" else "error_message"
        detail = phase.get(detail_key, "")
        message = f"Phase {phase_id} is {status}."
        if detail:
            message += f" {detail}"
        return False, message
    return False, f"Phase {phase_id} has invalid status {status!r}."


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Workroom Harness phases with an AI coding agent.")
    parser.add_argument("task", nargs="?", help="Task directory under .workroom/phases/. If omitted, auto-select one planned task.")
    parser.add_argument(
        "--agent",
        choices=["auto", "codex", "claude"],
        default="auto",
        help="Agent runner to use. auto prefers Codex, then Claude.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the first prompt without calling an agent")
    args = parser.parse_args()

    task_name = resolve_task_name(args.task)
    if not task_name:
        return 1

    task_dir = WORKROOM_DIR / "phases" / task_name
    index_path = task_dir / "index.json"

    if not index_path.exists():
        print(f"ERROR: {index_path.relative_to(ROOT)} not found")
        return 1

    phase_errors = validate_task(task_dir) + validate_top_index(task_dir)
    if phase_errors:
        print("ERROR: phase plan validation failed")
        for error in phase_errors:
            print(f"- {error}")
        return 1

    agent = resolve_agent(args.agent)

    if not args.dry_run and not check_agent(agent):
        print("ERROR: No supported agent CLI found. Install Codex or Claude, or use --dry-run.")
        return 1

    index = read_json(index_path)
    if args.dry_run:
        phase, previous_summaries = first_runnable_phase(index)
        if not phase:
            print(f"No pending phases in .workroom/phases/{task_name}")
            return 0

        can_start, reason = phase_can_start(phase)
        if not can_start:
            print(f"ERROR: {reason}")
            return 1

        phase_file = task_dir / phase["file"]
        if not phase_file.exists():
            print(f"ERROR: missing phase file {phase_file.relative_to(ROOT)}")
            return 1

        print("# Dry run: no files were written and no agent was called.")
        print()
        print(phase_prompt(None, task_name, phase_file, previous_summaries))
        return 0

    index.setdefault("started_at", stamp())
    write_json(index_path, index)
    update_top_index(task_name, "running")

    previous_summaries: list[str] = []

    for phase in index.get("phases", []):
        if phase.get("status") == "completed":
            if phase.get("summary"):
                previous_summaries.append(f"{phase['id']}: {phase['summary']}")
            continue

        can_start, reason = phase_can_start(phase)
        if not can_start:
            print(f"ERROR: {reason}")
            status = str(phase.get("status", "error"))
            update_top_index(task_name, status if status in STOP_PHASE_STATUSES else "error")
            return 1

        phase_file = task_dir / phase["file"]
        if not phase_file.exists():
            print(f"ERROR: missing phase file {phase_file.relative_to(ROOT)}")
            update_top_index(task_name, "error")
            return 1

        context_path = write_context_snapshot(task_dir)
        prompt = phase_prompt(context_path, task_name, phase_file, previous_summaries)
        if args.dry_run:
            print(prompt)
            return 0

        retries = int(phase.get("retries", 0))
        feedback = ""
        while retries < MAX_RETRIES:
            print(f"Running {phase['id']}: {phase['title']} with {agent} (attempt {retries + 1}/{MAX_RETRIES})")
            log_path = task_dir / f"{phase['id']}.worker.{retries + 1}.log"
            set_phase_status(
                index_path,
                phase["id"],
                "running",
                attempt=retries + 1,
                log=str(log_path.relative_to(ROOT)),
            )
            active_prompt = (
                fix_prompt(context_path, task_name, phase_file, previous_summaries, feedback)
                if feedback
                else prompt
            )
            code, worker_output = run_agent(agent, active_prompt, log_path)

            if code == 0:
                current_status = phase_status(index_path, phase["id"])
                if current_status == "blocked":
                    update_top_index(task_name, "blocked")
                    return 1
                if current_status == "error":
                    update_top_index(task_name, "error")
                    return 1

                verify_code, verify_output = run([str(WORKROOM_DIR / "scripts/verify.sh")], task_dir / f"{phase['id']}.verify.log")
                if verify_code == 0:
                    review_log_path = task_dir / f"{phase['id']}.review.{retries + 1}.log"
                    set_phase_status(
                        index_path,
                        phase["id"],
                        "reviewing",
                        attempt=retries + 1,
                        log=str(review_log_path.relative_to(ROOT)),
                    )
                    review_code, review_output = run_agent(
                        agent,
                        review_prompt(
                            context_path,
                            task_name,
                            phase_file,
                            verify_output,
                            previous_summaries,
                            current_change_snapshot(),
                        ),
                        review_log_path,
                        read_only=True,
                        output_schema=REVIEW_SCHEMA,
                    )
                    if review_code != 0:
                        if is_agent_infrastructure_failure(agent, review_output):
                            return abort_agent_infrastructure_failure(agent, review_output, review_log_path, index_path, phase["id"])
                        feedback = "Review agent failed to run.\n\n" + review_output
                        print(feedback)
                    else:
                        review_result = parse_review_result(review_output)
                        if review_result is None:
                            return abort_agent_infrastructure_failure(
                                agent,
                                "ERROR: Review agent returned invalid structured JSON.\n\n" + review_output,
                                review_log_path,
                                index_path,
                                phase["id"],
                            )
                        if review_result["decision"] == "APPROVED":
                            print(f"Review approved {phase['id']}")
                            index = read_json(index_path)
                            for item in index["phases"]:
                                if item["id"] == phase["id"]:
                                    item["status"] = "completed"
                                    item["completed_at"] = stamp()
                                    item["summary"] = extract_phase_summary(worker_output, f"{phase['title']} completed")
                                    previous_summaries.append(f"{phase['id']}: {item['summary']}")
                                    break
                            write_json(index_path, index)
                            break

                        feedback = review_feedback(review_result)
                        print(feedback)
                else:
                    feedback = "Verification failed.\n\n" + verify_output
                    print(verify_output)
            else:
                if is_agent_infrastructure_failure(agent, worker_output):
                    return abort_agent_infrastructure_failure(agent, worker_output, log_path, index_path, phase["id"])
                feedback = "Worker agent failed.\n\n" + worker_output

            index = read_json(index_path)
            current = next(item for item in index["phases"] if item["id"] == phase["id"])
            if current.get("status") == "blocked":
                update_top_index(task_name, "blocked")
                return 1
            if current.get("status") == "error":
                update_top_index(task_name, "error")
                return 1

            retries += 1
            current["retries"] = retries
            current["status"] = "retrying"
            write_json(index_path, index)

        index = read_json(index_path)
        current = next(item for item in index["phases"] if item["id"] == phase["id"])
        if current.get("status") != "completed":
            current["status"] = "error"
            current["failed_at"] = stamp()
            current["error_message"] = f"Phase did not receive verification and review approval after {MAX_RETRIES} attempts"
            write_json(index_path, index)
            update_top_index(task_name, "error")
            return 1

    index = read_json(index_path)
    index["status"] = "completed"
    index["completed_at"] = stamp()
    write_json(index_path, index)
    update_top_index(task_name, "completed")
    print(f"Completed .workroom/phases/{task_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
