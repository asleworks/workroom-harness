# Review Workflow

Use this workflow as a review gate for docs, phase plans, and implementation.

## Modes

### Docs Review

Read:

- `.workroom/AGENTS.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`

Check:

1. PRD goal, users, MVP scope, out-of-scope, and success criteria
2. explicit non-goals, constraints, assumptions, and edge cases
3. decision boundaries for what agents may decide without asking
4. clear ask-before-deciding rules for scope, auth, payment, persistence, deployment, dependencies, and external services
5. architecture stack, boundaries, data flow, and forbidden dependencies
6. ADR decisions, tradeoffs, and status
7. test strategy with realistic local checks
8. consistency between `.workroom/AGENTS.md` and `.workroom/docs/`

### Phase Review

Read:

- `.workroom/AGENTS.md`
- all files in `.workroom/docs/`
- `.workroom/phases/{task-name}/index.json`
- every `.workroom/phases/{task-name}/phase-*.md`

Check:

1. phases are ordered by dependency
2. each phase is small enough for a fresh worker run
3. each phase has concrete work, acceptance criteria, and verification
4. likely files to modify are concrete paths or directories
5. phase ids and file names are sequential and match `index.json`
6. `.workroom/phases/index.json` contains the task
7. docs updates happen before implementation when needed
8. no placeholder content remains
9. blocked external requirements are explicit
10. no phase implements out-of-scope PRD items
11. manual UI/dev-server checks are not the only blocking completion condition unless the user explicitly requested manual approval

### Implementation Review

Read:

- `.workroom/AGENTS.md`
- `.workroom/docs/PRD.md`
- `.workroom/docs/ARCHITECTURE.md`
- `.workroom/docs/ADR.md`
- `.workroom/docs/TEST_STRATEGY.md`
- current phase file
- changed files
- verification output

Check:

1. PRD scope compliance
2. out-of-scope feature creep
3. architecture rule compliance
4. unnecessary dependency additions
5. missing tests
6. type safety
7. error handling
8. maintainability
9. security-sensitive changes

Harness-owned phase index fields are not implementation deliverables. In implementation review, do not request changes only because the current phase lacks `status: completed`, `completed_at`, or `summary`; the harness writes those after approval.

Do not require a worker to mark a phase blocked because local verification, dev-server commands, browser checks, or manual UI checks could not run inside the worker session. Treat skipped local checks as review context. Request concrete code/test fixes when needed, or approve when the phase satisfies acceptance criteria and harness verification passed.

Treat `deferred_requirements` as acceptable when they are post-implementation actions, such as adding an API key for real external traffic or running a manual production check. Do not reject otherwise complete work only because those deferred actions remain.

## Output Format

Write a natural-language review. Do not edit files during review.

Include:

- what you inspected
- blocking issues, if any
- missing verification, if any
- architecture or scope concerns, if any
- concrete fixes the worker or planner should make
- non-blocking risks, if useful

End with exactly one decision line:

```text
REVIEW_DECISION: APPROVED
```

or

```text
REVIEW_DECISION: CHANGES_REQUESTED
```

## Decision Rules

- Use `REVIEW_DECISION: APPROVED` only when the reviewed artifact satisfies the relevant mode criteria.
- Use `REVIEW_DECISION: CHANGES_REQUESTED` when docs, phase files, code, tests, or behavior must change before approval.
- When requesting changes, explain the concrete fixes in natural language.
- When approving, still mention any non-blocking risks or deferred requirements that future agents should know.
- Keep review findings concrete enough for a worker agent to fix without asking for interpretation.
- Do not edit files during review. Review is read-only.
