# Workroom Harness

An AI coding-agent harness for Codex and Claude Code.

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
.claude/skills/   Claude Code skills
```

## Install

Codex:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-codex.sh | bash
```

Claude Code:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-claude.sh | bash
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

For a Claude-only install, use the Claude installer with the same flag:

```bash
curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-claude.sh | bash -s -- --overwrite
```

`--overwrite` updates harness-owned scripts, workflows, templates, and skills. It preserves project state files: `.workroom/AGENTS.md`, `.workroom/docs/`, `.workroom/phases/`, and `.workroom/scripts/verify.sh`.

## Workflow

Codex:

```text
$workroom-plan
$workroom-phase
$workroom-harness
```

Claude Code:

```text
/workroom-plan
/workroom-phase
/workroom-harness
```

The flow is:

```text
fill docs
-> fresh docs reviewer
-> create phases
-> fresh phase-plan reviewer
-> run phases through worker/verify/reviewer/fix loops
```

Codex uses `codex exec`. Claude Code uses `claude -p` with `--permission-mode bypassPermissions` by default so non-interactive workers do not stop waiting for command approval. Set `WORKROOM_CLAUDE_PERMISSION_MODE` to override this.

If verification or review fails, the harness feeds the failure back to the worker and keeps trying while the failure or repository diff is changing. It pauses only when attempts stall on the same failure and same repository state, or when the per-phase safety budget is exhausted. The phase is left `pending` with `last_failure_reason` and `last_failure_log`; this retryable pause is not a CLI error unless `--strict-exit-codes` is used.

Routine compiler, lint, test, and review failures are fed back to the worker internally. By default the harness prints concise retry progress and log paths instead of dumping the full failure output on every attempt. Use `--verbose` when you need full per-attempt output in the terminal.

Agent CLI and session-permission issues are checked before phase work starts when possible. Verification failures caused only by external setup, such as API keys, secrets, account connections, command approval, or manual checks, are recorded as `deferred_requirements` instead of blocking implementation mid-run.

Review agents write natural-language findings and end with `REVIEW_DECISION: APPROVED` or `REVIEW_DECISION: CHANGES_REQUESTED`. The harness parses only that decision line and passes the review text through as feedback.

Check current harness state without searching for processes or logs:

```bash
python3 .workroom/scripts/workroom_status.py
```

Post-implementation actions such as filling API keys, connecting accounts, or running manual external checks should be recorded as `deferred_requirements`. The harness can finish as `completed_with_deferred_requirements` and print those actions at the end instead of blocking midway.
