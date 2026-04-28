#!/usr/bin/env python3

import codecs
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


def resolve_agent(agent: str) -> str:
    if agent != "auto":
        return agent
    if shutil.which("codex"):
        return "codex"
    return "none"


def check_agent(agent: str) -> bool:
    if agent == "codex":
        return shutil.which("codex") is not None
    return False


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


def run_codex_agent(root: Path, prompt: str, log_path: Path, read_only: bool = False) -> tuple[int, str]:
    return run_streaming(
        [
            "codex",
            "--ask-for-approval",
            "never",
            "exec",
            "--cd",
            str(root),
            "--sandbox",
            "read-only" if read_only else "workspace-write",
            "--ephemeral",
            "-",
        ],
        log_path,
        input_text=prompt,
        cwd=root,
    )


def is_agent_infrastructure_failure(agent: str, output: str) -> bool:
    if agent == "codex" and CODEX_SESSION_ACCESS_ERROR in output:
        return True
    if AGENT_IDLE_TIMEOUT_ERROR in output or AGENT_TOTAL_TIMEOUT_ERROR in output:
        return True
    return False
