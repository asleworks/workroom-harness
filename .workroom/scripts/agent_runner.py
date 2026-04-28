#!/usr/bin/env python3

import codecs
import json
import os
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
REVIEW_RESULT_KEYS = {
    "decision",
    "summary",
    "blocking_issues",
    "missing_tests",
    "architecture_violations",
    "recommended_fixes",
}
REVIEW_RESULT_ARRAY_KEYS = {
    "blocking_issues",
    "missing_tests",
    "architecture_violations",
    "recommended_fixes",
}


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


def parse_review_result(output: str) -> dict | None:
    try:
        data = json.loads(output)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    if set(data.keys()) != REVIEW_RESULT_KEYS:
        return None
    if data.get("decision") not in {"APPROVED", "CHANGES_REQUESTED"}:
        return None
    if not isinstance(data.get("summary"), str):
        return None
    for key in REVIEW_RESULT_ARRAY_KEYS:
        value = data.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return None
    actionable_items = [
        item.strip()
        for key in REVIEW_RESULT_ARRAY_KEYS
        for item in data[key]
        if item.strip()
    ]
    if data["decision"] == "CHANGES_REQUESTED" and not actionable_items:
        return None
    if data["decision"] == "APPROVED" and actionable_items:
        return None
    return data


def normalize_structured_output(output: str) -> str:
    try:
        envelope = json.loads(output)
    except Exception:
        return output

    if not isinstance(envelope, dict):
        return output

    structured_output = envelope.get("structured_output")
    if isinstance(structured_output, dict):
        return json.dumps(structured_output, ensure_ascii=False)

    result = envelope.get("result")
    if isinstance(result, str) and result.strip():
        try:
            json.loads(result)
            return result
        except Exception:
            return output

    return output


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
    output_schema: Path | None = None,
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
    if output_schema is not None:
        command.extend(["--output-schema", str(output_schema)])
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
    output_schema: Path | None = None,
) -> tuple[int, str]:
    command = ["claude", "-p"]
    if CLAUDE_PERMISSION_MODE:
        command.extend(["--permission-mode", CLAUDE_PERMISSION_MODE])
    if output_schema is not None:
        command.extend([
            "--output-format",
            "json",
            "--json-schema",
            output_schema.read_text(encoding="utf-8"),
        ])
    if read_only:
        with tempfile.TemporaryDirectory(prefix="workroom-review-") as tmp_dir:
            review_root = Path(tmp_dir) / root.name
            shutil.copytree(root, review_root, ignore=ignore_read_only_copy_items, symlinks=False)
            code, output = run_streaming(command, log_path, input_text=prompt, cwd=review_root)
    else:
        code, output = run_streaming(command, log_path, input_text=prompt, cwd=root)

    if output_schema is not None and code == 0:
        return code, normalize_structured_output(output)
    return code, output


def run_agent(
    agent: str,
    root: Path,
    prompt: str,
    log_path: Path,
    read_only: bool = False,
    output_schema: Path | None = None,
) -> tuple[int, str]:
    if agent == "codex":
        return run_codex_agent(root, prompt, log_path, read_only=read_only, output_schema=output_schema)
    if agent == "claude":
        return run_claude_agent(root, prompt, log_path, read_only=read_only, output_schema=output_schema)
    return 1, f"Unsupported agent: {agent}"


def is_agent_infrastructure_failure(agent: str, output: str) -> bool:
    if agent == "codex" and CODEX_SESSION_ACCESS_ERROR in output:
        return True
    if AGENT_IDLE_TIMEOUT_ERROR in output or AGENT_TOTAL_TIMEOUT_ERROR in output:
        return True
    return False
