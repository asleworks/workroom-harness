#!/usr/bin/env python3

import re
from pathlib import Path


WORKROOM_DIR = Path(__file__).resolve().parent.parent
ROOT = WORKROOM_DIR.parent

REQUIRED_DOCS = {
    ".workroom/docs/PRD.md": [
        "Goal",
        "Target Users",
        "MVP",
        "Out of Scope",
        "Constraints",
        "Assumptions",
        "Decision Boundaries",
        "Edge Cases",
        "Success Criteria",
    ],
    ".workroom/docs/ARCHITECTURE.md": [
        "Tech Stack",
        "Directory Structure",
        "Architecture Rules",
        "Data Flow",
    ],
    ".workroom/docs/ADR.md": [
        "Status",
        "Context",
        "Decision",
        "Consequences",
    ],
    ".workroom/docs/TEST_STRATEGY.md": [
        "Goal",
        "Required Checks",
        "Test Scope",
    ],
}

PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"프로젝트 이름을 입력하세요",
    r"(?m)^Write the project name here\.$",
    r"(?m)^-\s*User group \d+\s*$",
    r"(?m)^\d+\.\s*Core feature \d+\s*$",
    r"(?m)^-\s*\[\s*\]\s*Feature [A-Z]\s*$",
    r"(?m)^Describe the problem this project solves\.$",
    r"(?m)^-\s*Replace this.*$",
    r"Workroom Harness Project",
    r"Build a small, scoped, verifiable software project with AI assistance\.",
    r"project maintainers and AI coding agents",
    r"(?m)^-\s*Assumption \d+\s*$",
]

EMPTY_FIELD_PATTERNS = [
    r"(?m)^-\s*Framework:\s*$",
    r"(?m)^-\s*Language:\s*$",
    r"(?m)^-\s*Styling:\s*$",
    r"(?m)^-\s*Database:\s*$",
    r"(?m)^-\s*External APIs:\s*$",
    r"(?m)^-\s*Technical constraints:\s*$",
    r"(?m)^-\s*Data or API constraints:\s*$",
    r"(?m)^-\s*Authentication constraints:\s*$",
    r"(?m)^-\s*Deployment constraints:\s*$",
    r"(?m)^-\s*Budget or time constraints:\s*$",
]


def validate_file(relative_path: str, required_markers: list[str]) -> list[str]:
    path = ROOT / relative_path
    errors: list[str] = []

    if not path.exists():
        return [f"missing {relative_path}"]

    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if len(stripped) < 120:
        errors.append(f"{relative_path}: document is too thin")

    for marker in required_markers:
        if marker.lower() not in text.lower():
            errors.append(f"{relative_path}: missing section or marker {marker!r}")

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            errors.append(f"{relative_path}: placeholder remains: {pattern}")

    for pattern in EMPTY_FIELD_PATTERNS:
        if re.search(pattern, text):
            errors.append(f"{relative_path}: empty field remains: {pattern}")

    return errors


def validate_agents() -> list[str]:
    errors: list[str] = []
    agents = ROOT / ".workroom/AGENTS.md"
    if not agents.exists():
        return ["missing .workroom/AGENTS.md"]

    text = agents.read_text(encoding="utf-8")
    for marker in ["Project Profile", "Project Rules", "Decision Boundaries", "Architecture Boundaries", "Verification"]:
        if marker.lower() not in text.lower():
            errors.append(f".workroom/AGENTS.md: missing section {marker!r}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(validate_agents())
    for path, markers in REQUIRED_DOCS.items():
        errors.extend(validate_file(path, markers))

    if errors:
        for error in errors:
            print(f"FAIL  {error}")
        return 1

    print("Docs are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
