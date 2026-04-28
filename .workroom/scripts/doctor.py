#!/usr/bin/env python3

from pathlib import Path
import json
import os
import subprocess
import sys


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent

REQUIRED_FILES = [
    ".workroom/AGENTS.md",
    ".workroom/docs/PRD.md",
    ".workroom/docs/ARCHITECTURE.md",
    ".workroom/docs/ADR.md",
    ".workroom/docs/TEST_STRATEGY.md",
    ".workroom/workflows/plan.md",
    ".workroom/workflows/phase.md",
    ".workroom/workflows/harness.md",
    ".workroom/workflows/review.md",
    ".workroom/workflows/fix.md",
    ".workroom/scripts/verify.sh",
    ".workroom/scripts/validate_docs.py",
    ".workroom/scripts/scaffold_phases.py",
    ".workroom/scripts/review_artifacts.py",
    ".workroom/scripts/validate_phases.py",
    ".workroom/scripts/install-codex.sh",
    ".workroom/scripts/install.py",
    ".workroom/scripts/run_phases.py",
    ".workroom/templates/phase-index.template.json",
    ".workroom/templates/phase.template.md",
]


def check_file(path: str) -> bool:
    exists = (ROOT / path).is_file()
    print(f"{'OK' if exists else 'MISS'}  {path}")
    return exists


def check_json_files() -> bool:
    ok = True
    for path in ROOT.rglob("*.json"):
        if ".git" in path.parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            print(f"OK    valid json: {path.relative_to(ROOT)}")
        except Exception as exc:
            print(f"FAIL  invalid json: {path.relative_to(ROOT)} ({exc})")
            ok = False
    return ok


def check_verify() -> bool:
    verify = WORKROOM_DIR / "scripts/verify.sh"
    executable = os.access(verify, os.X_OK)
    print(f"{'OK' if executable else 'WARN'}  .workroom/scripts/verify.sh executable")

    result = subprocess.run(
        [str(verify)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    print(f"{'OK' if result.returncode == 0 else 'FAIL'}  .workroom/scripts/verify.sh exits {result.returncode}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode == 0


def check_docs() -> bool:
    result = subprocess.run(
        [sys.executable, str(WORKROOM_DIR / "scripts/validate_docs.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    print(f"{'OK' if result.returncode == 0 else 'WARN'}  project docs validation")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode == 0


def check_agents() -> bool:
    codex = subprocess.run(["which", "codex"], text=True, capture_output=True)

    if codex.returncode == 0:
        print(f"OK    codex CLI: {codex.stdout.strip()}")
    else:
        print("INFO  codex CLI not found")

    return codex.returncode == 0


def check_skill_set(name: str, paths: list[str]) -> bool:
    existing = [(ROOT / path).is_file() for path in paths]
    if not any(existing):
        print(f"INFO  optional {name} skills not installed")
        return False

    ok = True
    for path in paths:
        exists = (ROOT / path).is_file()
        print(f"{'OK' if exists else 'MISS'}  {name} skill: {path}")
        ok = ok and exists
    return ok


def check_skills() -> bool:
    codex_ok = check_skill_set(
        "codex",
        [
            ".agents/skills/workroom-phase/SKILL.md",
            ".agents/skills/workroom-plan/SKILL.md",
            ".agents/skills/workroom-harness/SKILL.md",
        ],
    )
    return codex_ok


def main() -> int:
    print("Workroom Harness doctor\n")

    files_ok = True
    for path in REQUIRED_FILES:
        files_ok = check_file(path) and files_ok
    skills_ok = check_skills()
    json_ok = check_json_files()
    verify_ok = check_verify()
    docs_ok = check_docs()
    agent_ok = check_agents()

    print()
    if files_ok and skills_ok and json_ok and verify_ok and docs_ok and agent_ok:
        print("Workroom Harness is ready.")
        return 0

    if files_ok and skills_ok and json_ok and verify_ok and docs_ok:
        print("Workroom Harness docs and files are ready. Install Codex CLI to run phases automatically.")
        return 0

    if files_ok and skills_ok and json_ok and verify_ok:
        print("Workroom Harness is installed. Run workroom-plan before phase planning or harness execution.")
        return 0

    print("Workroom Harness needs attention.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
