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

## Output Format

```markdown
# Review Result

REVIEW_DECISION: APPROVED
```

or:

```markdown
# Review Result

REVIEW_DECISION: CHANGES_REQUESTED

## Summary

## Blocking Issues

## Non-blocking Suggestions

## Missing Tests

## Architecture Violations

## Recommended Fixes
```

## Decision Rules

- Use `REVIEW_DECISION: APPROVED` only when the reviewed artifact satisfies the relevant mode criteria.
- Use `REVIEW_DECISION: CHANGES_REQUESTED` when docs, phase files, code, tests, or behavior must change before approval.
- Keep review findings concrete enough for a worker agent to fix without asking for interpretation.
- Do not edit files during review. Review is read-only.
