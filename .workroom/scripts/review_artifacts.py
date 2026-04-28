#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_runner import check_agent, is_agent_infrastructure_failure, parse_review_result, resolve_agent, run_agent


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def run_reviewer(agent: str, prompt: str, log_path: Path) -> tuple[int, str]:
    return run_agent(agent, ROOT, prompt, log_path, read_only=True)


def docs_prompt() -> str:
    return """You are the Workroom Harness docs review agent.

Review the Workroom project docs in read-only mode. Do not edit files.

## Required Reads

- `.workroom/AGENTS.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`
- `.workroom/workflows/review.md`

## Review Mode

Use `.workroom/workflows/review.md` in docs mode.

## Required Review Output

Write a natural-language review. Include the concrete issues and fixes when changes are needed.
End with exactly one decision line:

`REVIEW_DECISION: APPROVED`

or

`REVIEW_DECISION: CHANGES_REQUESTED`

Use `APPROVED` only if there are no blocking issues and the docs are ready for phase planning.
Use `CHANGES_REQUESTED` if the planning agent must change anything before phase planning.
"""


def phases_prompt(task_name: str) -> str:
    task_dir = WORKROOM_DIR / "phases" / task_name
    return f"""You are the Workroom Harness phase-plan review agent.

Review the generated phase plan in read-only mode. Do not edit files.

## Required Reads

- `.workroom/AGENTS.md`
- all files in `.workroom/docs/`
- `.workroom/workflows/review.md`
- `.workroom/phases/index.json`
- `.workroom/phases/{task_name}/index.json`
- every `.workroom/phases/{task_name}/phase-*.md`

## Review Mode

Use `.workroom/workflows/review.md` in phases mode.

## Task Directory

`{task_dir.relative_to(ROOT)}`

## Required Review Output

Write a natural-language review. Include the concrete issues and fixes when changes are needed.
End with exactly one decision line:

`REVIEW_DECISION: APPROVED`

or

`REVIEW_DECISION: CHANGES_REQUESTED`

Use `APPROVED` only if there are no blocking issues and the phase plan is executable by fresh worker agents.
Use `CHANGES_REQUESTED` if the planning agent must change any phase file or phase index before harness execution.
"""


def decision_code(output: str) -> int:
    result = parse_review_result(output)
    if result is None:
        return 1
    if result["decision"] == "APPROVED":
        return 0
    if result["decision"] == "CHANGES_REQUESTED":
        return 2
    return 1


def review_exit_code(decision: int, strict_exit_codes: bool) -> int:
    if decision == 0:
        return 0
    if decision == 2:
        return 2 if strict_exit_codes else 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a fresh read-only Workroom review agent.")
    parser.add_argument("mode", choices=["docs", "phases"], help="Artifact type to review")
    parser.add_argument("task", nargs="?", help="Task directory under .workroom/phases for phases mode")
    parser.add_argument(
        "--agent",
        choices=["auto", "codex", "claude"],
        default="auto",
        help="Reviewer agent to use. auto prefers Codex, then Claude.",
    )
    parser.add_argument(
        "--strict-exit-codes",
        action="store_true",
        help="Return exit code 2 for CHANGES_REQUESTED. By default, any valid review decision exits 0.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the reviewer prompt without calling an agent")
    args = parser.parse_args()

    if args.mode == "phases" and not args.task:
        print("ERROR: phases mode requires a task name, for example:")
        print("python3 .workroom/scripts/review_artifacts.py phases task-name")
        return 1

    if args.mode == "phases":
        task_name = args.task.strip().strip("/")
        task_dir = WORKROOM_DIR / "phases" / task_name
        if not args.dry_run and not task_dir.is_dir():
            print(f"ERROR: phase task directory not found: {task_dir.relative_to(ROOT)}")
            return 1
        prompt = phases_prompt(task_name)
        log_name = f"phases-{task_name}.{stamp()}.log"
    else:
        prompt = docs_prompt()
        log_name = f"docs.{stamp()}.log"

    if args.dry_run:
        print("# Dry run: no agent was called.")
        print()
        print(prompt)
        return 0

    agent = resolve_agent(args.agent)
    if not check_agent(agent):
        print("ERROR: No supported reviewer CLI found. Install Codex or Claude, or use --dry-run.")
        return 1

    log_path = WORKROOM_DIR / "reviews" / log_name
    code, output = run_reviewer(agent, prompt, log_path)
    if code != 0:
        print(output)
        if is_agent_infrastructure_failure(agent, output):
            print(
                f"\nReviewer runner failed before review could run. Fix the runner permission issue and rerun. Log: {log_path.relative_to(ROOT)}",
                file=sys.stderr,
            )
            return 1
        print(f"\nReview agent failed. Log: {log_path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    print(output)
    print(f"Review log: {log_path.relative_to(ROOT)}", file=sys.stderr)
    decision = decision_code(output)
    exit_code = review_exit_code(decision, args.strict_exit_codes)
    if exit_code == 1:
        print("ERROR: Review output must include REVIEW_DECISION: APPROVED or REVIEW_DECISION: CHANGES_REQUESTED.", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
