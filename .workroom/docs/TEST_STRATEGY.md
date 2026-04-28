# Test Strategy

## Goal

Tests are a feedback mechanism for AI agents. They allow the agent to verify work and fix failures without relying only on manual review.

## Required Checks

Run verification before marking work complete:

- lint
- typecheck
- unit tests
- build

The concrete commands live in `.workroom/scripts/verify.sh`.

## Test Scope

### UI Changes

- Main rendering path
- User input handling
- Empty and error states

### API Changes

- Successful response
- Invalid input
- Error response

### Business Logic Changes

- Core behavior
- Edge cases
- Failure cases

## When Tests May Be Skipped

Tests may be skipped for:

- documentation-only changes
- comments-only changes
- copy-only changes with no logic changes

If tests are skipped, explain why in the final summary.

