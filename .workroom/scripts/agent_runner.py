#!/usr/bin/env python3

import codecs
import json
import os
import re
import select
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


CODEX_SESSION_ACCESS_ERROR = "Codex cannot access session files"
AGENT_IDLE_TIMEOUT_ERROR = "agent runner produced no output"
AGENT_TOTAL_TIMEOUT_ERROR = "agent runner exceeded total timeout"
READ_ONLY_COPY_IGNORE_NAMES = {
    ".DS_Store",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
}
READ_ONLY_COPY_IGNORE_SUFFIXES = {
    ".log",
    ".log.final",
}


def int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return max(0, int(value))
    except ValueError:
        return default


AGENT_IDLE_TIMEOUT_SECONDS = int_env("WORKROOM_AGENT_IDLE_TIMEOUT_SECONDS", 0)
AGENT_TOTAL_TIMEOUT_SECONDS = int_env("WORKROOM_AGENT_TOTAL_TIMEOUT_SECONDS", 7200)
CLAUDE_PERMISSION_MODE = os.environ.get("WORKROOM_CLAUDE_PERMISSION_MODE", "bypassPermissions").strip()
REVIEW_DECISION_PATTERN = re.compile(r"(?im)^\s*REVIEW_DECISION\s*:\s*(APPROVED|CHANGES_REQUESTED)\s*$")


def resolve_agent(agent: str) -> str:
    if agent != "auto":
        return agent
    if shutil.which("codex"):
        return "codex"
    if shutil.which("claude"):
        return "claude"
    return "none"


def check_agent(agent: str) -> bool:
    if agent == "codex":
        return shutil.which("codex") is not None
    if agent == "claude":
        return shutil.which("claude") is not None
    return False


def ignore_read_only_copy_items(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    base = Path(directory)
    for name in names:
        path = base / name
        if name in READ_ONLY_COPY_IGNORE_NAMES or any(name.endswith(suffix) for suffix in READ_ONLY_COPY_IGNORE_SUFFIXES):
            ignored.add(name)
        elif path.is_symlink():
            ignored.add(name)
    return ignored


def review_text_from_output(output: str) -> str:
    try:
        envelope = json.loads(output)
    except Exception:
        return output

    if not isinstance(envelope, dict):
        return output

    result = envelope.get("result")
    if isinstance(result, str) and result.strip():
        return result

    structured_output = envelope.get("structured_output")
    if isinstance(structured_output, dict):
        return json.dumps(structured_output, indent=2, ensure_ascii=False)

    return output


def legacy_json_review_text(data: dict) -> str:
    decision = data.get("decision")
    if decision not in {"APPROVED", "CHANGES_REQUESTED"}:
        return ""

    body = json.dumps(data, indent=2, ensure_ascii=False)
    return f"{body}\n\nREVIEW_DECISION: {decision}"


def parse_review_result(output: str) -> dict | None:
    text = review_text_from_output(output).strip()

    try:
        data = json.loads(text)
    except Exception:
        data = None
    if isinstance(data, dict):
        legacy_text = legacy_json_review_text(data)
        if legacy_text:
            text = legacy_text

    matches = list(REVIEW_DECISION_PATTERN.finditer(text))
    if not matches:
        return None

    decision = matches[-1].group(1)
    return {
        "decision": decision,
        "feedback": text,
    }


def kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError:
            process.kill()
        process.wait(timeout=5)


def run_streaming(
    command: list[str],
    log_path: Path,
    input_text: str | None = None,
    cwd: Path | None = None,
    idle_timeout_seconds: int = AGENT_IDLE_TIMEOUT_SECONDS,
    total_timeout_seconds: int = AGENT_TOTAL_TIMEOUT_SECONDS,
) -> tuple[int, str]:
    started_at = time.monotonic()
    last_output_at = started_at
    output_parts: list[str] = []
    log_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_file = tempfile.TemporaryFile("w+b") if input_text is not None else None

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(command)}\n")
        log.write(f"idle_timeout_seconds: {idle_timeout_seconds or 'disabled'}\n")
        log.write(f"total_timeout_seconds: {total_timeout_seconds or 'disabled'}\n\n")
        if input_text is not None and prompt_file is not None:
            encoded_input = input_text.encode("utf-8")
            prompt_file.write(encoded_input)
            prompt_file.seek(0)
            log.write(f"stdin_bytes: {len(encoded_input)}\n\n")
        log.flush()

        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=prompt_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        if prompt_file is not None:
            prompt_file.close()
            prompt_file = None

        assert process.stdout is not None
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            now = time.monotonic()
            if process.poll() is not None:
                remainder_bytes = process.stdout.read()
                remainder = decoder.decode(remainder_bytes or b"", final=True)
                if remainder:
                    output_parts.append(remainder)
                    log.write(remainder)
                    log.flush()
                break

            if total_timeout_seconds > 0 and now - started_at > total_timeout_seconds:
                message = f"\nERROR: agent runner exceeded total timeout of {total_timeout_seconds} seconds.\n"
                output_parts.append(message)
                log.write(message)
                log.flush()
                kill_process_group(process)
                return 124, "".join(output_parts)

            if idle_timeout_seconds > 0 and now - last_output_at > idle_timeout_seconds:
                message = f"\nERROR: agent runner produced no output for {idle_timeout_seconds} seconds.\n"
                output_parts.append(message)
                log.write(message)
                log.flush()
                kill_process_group(process)
                return 124, "".join(output_parts)

            readable, _, _ = select.select([process.stdout], [], [], 1)
            if not readable:
                continue

            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                continue
            text = decoder.decode(chunk)
            last_output_at = time.monotonic()
            output_parts.append(text)
            log.write(text)
            log.flush()

        return process.returncode or 0, "".join(output_parts)


def run_codex_agent(
    root: Path,
    prompt: str,
    log_path: Path,
    read_only: bool = False,
) -> tuple[int, str]:
    final_message_path = log_path.with_suffix(log_path.suffix + ".final")
    command = [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--cd",
        str(root),
        "--sandbox",
        "read-only" if read_only else "workspace-write",
        "--ephemeral",
        "--output-last-message",
        str(final_message_path),
    ]
    command.append("-")
    code, transcript = run_streaming(
        command,
        log_path,
        input_text=prompt,
        cwd=root,
    )
    if code == 0 and final_message_path.exists():
        final_message = final_message_path.read_text(encoding="utf-8")
        if final_message.strip():
            return code, final_message
    return code, transcript


def run_claude_agent(
    root: Path,
    prompt: str,
    log_path: Path,
    read_only: bool = False,
) -> tuple[int, str]:
    command = ["claude", "-p"]
    if CLAUDE_PERMISSION_MODE:
        command.extend(["--permission-mode", CLAUDE_PERMISSION_MODE])
    if read_only:
        with tempfile.TemporaryDirectory(prefix="workroom-review-") as tmp_dir:
            review_root = Path(tmp_dir) / root.name
            shutil.copytree(root, review_root, ignore=ignore_read_only_copy_items, symlinks=False)
            code, output = run_streaming(command, log_path, input_text=prompt, cwd=review_root)
    else:
        code, output = run_streaming(command, log_path, input_text=prompt, cwd=root)

    return code, output


def run_agent(
    agent: str,
    root: Path,
    prompt: str,
    log_path: Path,
    read_only: bool = False,
) -> tuple[int, str]:
    if agent == "codex":
        return run_codex_agent(root, prompt, log_path, read_only=read_only)
    if agent == "claude":
        return run_claude_agent(root, prompt, log_path, read_only=read_only)
    return 1, f"Unsupported agent: {agent}"


def is_agent_infrastructure_failure(agent: str, output: str) -> bool:
    if agent == "codex" and CODEX_SESSION_ACCESS_ERROR in output:
        return True
    if AGENT_IDLE_TIMEOUT_ERROR in output or AGENT_TOTAL_TIMEOUT_ERROR in output:
        return True
    return False
