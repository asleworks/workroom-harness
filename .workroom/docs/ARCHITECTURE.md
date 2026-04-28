# Architecture

## Tech Stack

- Framework:
- Language:
- Styling:
- Database:
- External APIs:

## Directory Structure

```text
src/
├── app/
├── components/
├── lib/
├── services/
├── types/
└── tests/
```

## Architecture Rules

- UI components must not call external APIs directly.
- External API calls must go through service or API route layers.
- Business logic should not be embedded directly in UI components.
- Shared types must live in `types/`.
- Do not introduce new top-level directories without updating this document.

## Data Flow

```text
User Action
  -> UI Component
  -> Service / API Route
  -> External API or Domain Logic
  -> Response
  -> UI Render
```

## Forbidden Dependencies

The following dependency directions are forbidden:

```text
components -> database
components -> external API
types -> components
```

