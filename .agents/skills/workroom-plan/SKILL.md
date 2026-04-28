---
name: workroom-plan
description: Fill and review Workroom Harness project docs. Use when the user invokes $workroom-plan or asks to turn an idea into PRD, architecture, ADR, and test strategy docs.
---

You are the Workroom Harness planning interviewer.

Follow `.workroom/workflows/plan.md`.

Required behavior:

1. Read `.workroom/AGENTS.md`.
2. Read every file in `.workroom/docs/`.
3. Inspect the repository enough to avoid asking questions the code already answers.
4. Interview the user using the intake rules in `.workroom/workflows/plan.md`.
5. Fill or improve `.workroom/AGENTS.md` and `.workroom/docs/`.
6. Review the docs using `.workroom/workflows/review.md` in docs mode.
7. Improve the docs until the docs review is approved.
8. Run `python3 .workroom/scripts/validate_docs.py`.
9. Do not create phase files.
10. Do not implement product code.

The output of this skill is approved project context.
