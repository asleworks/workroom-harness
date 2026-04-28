# Workroom Harness

An AI coding-agent harness for Codex.

All Workroom-owned files are installed under `.workroom/` so the harness does not collide with an existing project's `docs/`, `scripts/`, or `AGENTS.md`.

```text
.workroom/
├── AGENTS.md
├── docs/
├── workflows/
├── scripts/
├── phases/
└── templates/

.agents/skills/   Codex skills
```

## Install

Codex:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash
```

You can override the repository through an environment variable when testing a fork:

```bash
WORKROOM_HARNESS_REPO=your-account/workroom-harness \
  curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash
```

Check the installation:

```bash
python3 .workroom/scripts/doctor.py
```

On a fresh install, `doctor.py` may report that the harness is installed while project docs still need planning. That is expected before running `$workroom-plan`.

To update an existing install, rerun the installer with `--overwrite`:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash -s -- --overwrite
```

`--overwrite` updates harness-owned scripts, workflows, templates, and skills. It preserves project state files: `.workroom/AGENTS.md`, `.workroom/docs/`, `.workroom/phases/`, and `.workroom/scripts/verify.sh`.

## Workflow

Codex:

```text
$workroom-plan
$workroom-phase
$workroom-harness
```

The flow is:

```text
fill docs
-> fresh docs reviewer
-> create phases
-> fresh phase-plan reviewer
-> run phases through worker/verify/reviewer/fix loops
```

Codex uses `codex exec`.
