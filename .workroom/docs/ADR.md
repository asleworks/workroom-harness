# Architecture Decision Records

Use ADRs to record important architectural decisions so future agents understand why the project is structured this way.

## ADR-001: Keep MVP Scope Narrow

### Status

Accepted

### Context

AI coding agents may expand ambiguous requirements into unnecessary features.

### Decision

The MVP must include only the core user flow described in `.workroom/docs/PRD.md`.

### Consequences

- The project remains easier to verify.
- Unplanned feature expansion is easier to detect.
- Future feature additions should create or update ADRs when they change architecture.

