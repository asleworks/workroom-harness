# Plan Workflow

Use this workflow to turn a rough product idea into execution-ready project docs.

## Purpose

Do not implement and do not create phases. Interview the user, fill the project docs, review the docs, improve them, and stop only when the docs are ready for phase planning.

## 1. Load Existing Context

Read what exists:

- `.workroom/AGENTS.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`

If this is an existing project, inspect the repository enough to avoid asking the user questions the codebase already answers.

## 2. Interview

Start with a compact intake when the docs are mostly empty. Ask up to seven questions in one message so the user can answer naturally.

Initial intake questions should cover:

1. what the service should do in one sentence
2. target user and primary use case
3. the smallest useful MVP flow
4. explicit non-goals
5. technical constraints or preferred stack
6. external APIs, credentials, data, auth, payment, or deployment constraints
7. success criteria and failure cases

After the initial intake, ask follow-up questions one at a time.

Question order:

1. intent: why this should exist
2. target user and primary use case
3. desired end state
4. MVP scope
5. explicit non-goals
6. constraints: tech, time, data, APIs, auth, budget
7. decision boundaries: what the agent may decide without asking
8. success criteria
9. failure cases and edge cases
10. verification expectations

Rules:

- Ask about intent and boundaries before implementation details.
- Do not ask for codebase facts that can be discovered locally.
- Prefer concrete examples over abstract preferences.
- Keep asking while non-goals, success criteria, or decision boundaries are vague.
- When the user says "fill the docs" or "proceed", write the best possible docs with explicit assumptions instead of asking low-value questions.
- Do not move to phase planning.

## 3. Write Docs

Update only:

- `.workroom/AGENTS.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`

The docs must capture:

- what to build
- what not to build
- who it is for
- how success is judged
- which assumptions were made
- which constraints or external dependencies exist
- which edge cases must be handled
- which decisions agents may make without asking
- which architecture boundaries matter
- which decisions have already been made
- what tests/checks define completion

## 4. Docs Review Gate

Review the docs using `.workroom/workflows/review.md` in `docs` mode.

Check:

- PRD has goal, users, MVP scope, out-of-scope, success criteria
- PRD has constraints, assumptions, decision boundaries, and edge cases
- Architecture has stack, boundaries, data flow, forbidden dependency directions
- ADR records meaningful decisions and tradeoffs
- Test strategy defines realistic verification
- AGENTS rules match the project docs
- unresolved questions are explicit

If review returns `REVIEW_DECISION: CHANGES_REQUESTED`, improve the docs and review again.

## 5. Validate

Run:

```bash
python3 .workroom/scripts/validate_docs.py
```

Fix validation failures before finishing.

## Done

Stop when:

- docs review returns `REVIEW_DECISION: APPROVED`
- `python3 .workroom/scripts/validate_docs.py` passes
- no implementation or phase files were created
