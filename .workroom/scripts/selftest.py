#!/usr/bin/env python3

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_runner
import run_phases
import workroom_status
from agent_runner import ignore_read_only_copy_items, parse_review_result
from review_artifacts import decision_code, review_exit_code
from run_phases import (
    codex_session_access_errors,
    collect_deferred_requirements,
    convert_worker_stop_to_feedback,
    current_change_fingerprint,
    deferred_verification_reason,
    fix_prompt,
    is_deferable_blocked_reason,
    is_deferable_verification_failure,
    phase_prompt,
    previous_failure_section,
    progress_signature,
    record_deferred_requirement,
    report_retry_feedback,
    retryable_pause_exit_code,
    summarize_phase_failure,
    verification_feedback,
    write_json,
)


def review_payload(decision: str, issues: list[str] | None = None) -> str:
    body = "Reviewed files and checked acceptance criteria."
    if issues:
        body += "\n\nBlocking issues:\n" + "\n".join(f"- {item}" for item in issues)
    return f"{body}\n\nREVIEW_DECISION: {decision}"


def test_review_contract() -> None:
    approved = review_payload("APPROVED")
    changes = review_payload("CHANGES_REQUESTED", ["fix issue"])
    invalid = "Reviewed the work but forgot the machine-readable decision line."

    assert parse_review_result(approved) is not None
    assert parse_review_result(changes) is not None
    assert parse_review_result(invalid) is None
    assert decision_code(approved) == 0
    assert decision_code(changes) == 2
    assert review_exit_code(2, strict_exit_codes=False) == 0
    assert review_exit_code(2, strict_exit_codes=True) == 2


def test_agent_envelope_review_parsing() -> None:
    changes = review_payload("CHANGES_REQUESTED", ["fix issue"])
    result_envelope = json.dumps({"type": "result", "result": changes})

    assert decision_code(result_envelope) == 2


def test_read_only_copy_ignore() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        out = Path(tmp) / "out"
        root.mkdir()
        (root / "keep.txt").write_text("keep", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "skip.txt").write_text("skip", encoding="utf-8")
        (root / "phase.log").write_text("skip", encoding="utf-8")
        (root / "link").symlink_to(root / "keep.txt")

        shutil.copytree(root, out, ignore=ignore_read_only_copy_items, symlinks=False)

        assert (out / "keep.txt").is_file()
        assert not (out / "node_modules").exists()
        assert not (out / "phase.log").exists()
        assert not (out / "link").exists()


def test_harness_feedback_contract() -> None:
    verify_error = (
        "app/api/youtube-comments/handler.ts(62,48): error TS2339: "
        "Property error does not exist on type YouTubeUrlValidationResult."
    )
    feedback = verification_feedback(verify_error)

    assert summarize_phase_failure(feedback) == verify_error
    assert retryable_pause_exit_code(strict_exit_codes=False) == 0
    assert retryable_pause_exit_code(strict_exit_codes=True) == 1
    assert run_phases.MAX_ATTEMPTS >= 30
    assert run_phases.STALL_LIMIT >= 3

    prompt = fix_prompt(
        run_phases.ROOT / ".workroom/phases/example/context.md",
        "example",
        run_phases.ROOT / ".workroom/templates/phase.template.md",
        [],
        feedback,
        "## git diff --stat\nhandler.ts | 2 +-",
        "",
    )
    assert "Current Repository Change Snapshot" in prompt
    assert "Fix Requirements" in prompt
    assert "handler.ts" in prompt
    assert "Do not mark repeated verification or review failure as" in prompt
    assert "Do not mark this phase" in prompt
    assert "dev-server commands" in prompt
    assert "deferred_requirements" in prompt
    assert 'unrecoverable repeated failure: `"status": "error"`' not in prompt


def test_phase_prompt_status_contract() -> None:
    prompt = phase_prompt(
        run_phases.ROOT / ".workroom/phases/example/context.md",
        "example",
        run_phases.ROOT / ".workroom/templates/phase.template.md",
        [],
        "",
        "",
    )

    assert 'user action needed: `"status": "blocked"`' in prompt
    assert 'truly unrecoverable implementation problem: `"status": "error"`' in prompt
    assert "Do not mark repeated verification or review failure as" in prompt
    assert "dev-server commands" in prompt
    assert "deferred_requirements" in prompt
    assert 'repeated failure: `"status": "error"`' not in prompt


def test_claude_worker_permission_mode_default() -> None:
    if "WORKROOM_CLAUDE_PERMISSION_MODE" not in os.environ:
        assert agent_runner.CLAUDE_PERMISSION_MODE == "bypassPermissions"


def test_deferable_blocked_reasons() -> None:
    assert is_deferable_blocked_reason("YOUTUBE_API_KEY is required to verify real API calls")
    assert is_deferable_blocked_reason("local verification and dev-server manual UI checks require command approval")
    assert not is_deferable_blocked_reason("Need user to decide which pricing model to implement")
    assert not is_deferable_blocked_reason("Need user approval before adding a new dependency package")


def test_deferable_verification_failures() -> None:
    external_failure = "YOUTUBE_API_KEY environment variable is required for live API verification"
    type_failure = "app/api/route.ts(2,1): error TS2339: Property missing does not exist"

    assert is_deferable_verification_failure(external_failure)
    assert not is_deferable_verification_failure(type_failure)
    assert "YOUTUBE_API_KEY" in deferred_verification_reason(external_failure)


def test_record_deferred_requirement() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index_path = Path(tmp) / "index.json"
        index_path.write_text(
            json.dumps({"phases": [{"id": "phase-01", "status": "running"}]}),
            encoding="utf-8",
        )
        record_deferred_requirement(index_path, "phase-01", "Set YOUTUBE_API_KEY before live verification")
        record_deferred_requirement(index_path, "phase-01", "Set YOUTUBE_API_KEY before live verification")

        updated = json.loads(index_path.read_text(encoding="utf-8"))
        assert updated["phases"][0]["deferred_requirements"] == ["Set YOUTUBE_API_KEY before live verification"]


def test_atomic_json_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "index.json"
        write_json(path, {"phases": [{"id": "phase-01", "status": "running"}]})
        assert json.loads(path.read_text(encoding="utf-8"))["phases"][0]["id"] == "phase-01"
        assert not list(Path(tmp).glob(".*.tmp"))


def test_status_json_read_retries_during_update() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "index.json"
        path.write_text('{"phases": [', encoding="utf-8")

        def finish_write() -> None:
            time.sleep(0.05)
            path.write_text('{"phases": []}', encoding="utf-8")

        writer = threading.Thread(target=finish_write)
        writer.start()
        try:
            assert workroom_status.read_json(path, attempts=10, delay_seconds=0.02) == {"phases": []}
        finally:
            writer.join()


def test_deferred_requirements_are_collected() -> None:
    deferred = collect_deferred_requirements(
        {
            "phases": [
                {"id": "phase-01", "deferred_requirements": ["Set YOUTUBE_API_KEY in .env.local"]},
                {"id": "phase-02", "deferred_requirements": ["Run production smoke check"]},
            ]
        }
    )
    assert deferred == [
        "phase-01: Set YOUTUBE_API_KEY in .env.local",
        "phase-02: Run production smoke check",
    ]


def test_worker_stop_states_become_feedback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index_path = Path(tmp) / "index.json"
        index_path.write_text(
            json.dumps(
                {
                    "phases": [
                        {
                            "id": "phase-01",
                            "status": "error",
                            "error_message": "TypeScript failed during implementation",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = convert_worker_stop_to_feedback(index_path, "phase-01")
        assert result is not None
        message, feedback = result
        updated = json.loads(index_path.read_text(encoding="utf-8"))
        assert message == "Worker requested error."
        assert updated["phases"][0]["status"] == "retrying"
        assert "TypeScript failed" in feedback


def test_codex_session_preflight_detects_permission_issue() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "codex-home"
        sessions = home / "sessions"
        sessions.mkdir(parents=True)
        original_mode = sessions.stat().st_mode
        try:
            sessions.chmod(0)
            errors = codex_session_access_errors(home)
        finally:
            sessions.chmod(original_mode)

        assert errors
        assert "permission denied" in errors[0]


def test_retry_output_is_concise_by_default() -> None:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        report_retry_feedback(
            "Verification failed.",
            "Full verification output:\napp/api/route.ts(1,1): error TS1234",
            run_phases.ROOT / ".workroom/phases/example/phase-01.verify.log",
            verbose=False,
        )

    output = stream.getvalue()
    assert "Verification failed. Retrying with feedback." in output
    assert "phase-01.verify.log" in output
    assert "TS1234" not in output

    previous = previous_failure_section(
        {
            "last_failure_reason": "app/api/route.ts(1,1): error TS1234",
            "last_failure_log": ".workroom/phases/example/phase-01.verify.log",
        }
    )
    assert "Last failure log" in previous
    assert "phase-01.verify.log" in previous


def test_progress_tracking_contract() -> None:
    first = progress_signature("Verification failed.\n\napp/api/route.ts(1,1): error TS1234")
    same = progress_signature("Verification failed.\n\napp/api/route.ts(1,1): error TS1234")
    changed_failure = progress_signature("Verification failed.\n\napp/api/route.ts(2,1): error TS5678")

    assert first == same
    assert first != changed_failure


def test_untracked_file_changes_count_as_progress() -> None:
    path = run_phases.ROOT / ".workroom/.selftest-progress.tmp"
    try:
        path.write_text("first", encoding="utf-8")
        first = current_change_fingerprint()
        path.write_text("second", encoding="utf-8")
        second = current_change_fingerprint()
    finally:
        path.unlink(missing_ok=True)

    assert first != second


def test_legacy_contract_terms_do_not_return() -> None:
    legacy_terms = [
        "PHASE" + "_SUMMARY",
        "structured " + "JSON",
        "review " + "JSON",
        "valid " + "structured",
        "review" + "-result",
        "schemas" + "/review",
        "blocking" + "_issues",
        "missing" + "_tests",
        "architecture" + "_violations",
        "recommended" + "_fixes",
        "output" + "_schema",
        "REVIEW" + "_SCHEMA",
        "planned" + " or running",
    ]
    roots = [
        run_phases.ROOT / "README.md",
        run_phases.ROOT / ".workroom",
        run_phases.ROOT / ".agents",
        run_phases.ROOT / ".claude",
    ]
    offenders: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in paths:
            if ".git" in path.parts or "__pycache__" in path.parts or path.name == "selftest.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for term in legacy_terms:
                if term in text:
                    offenders.append(f"{path.relative_to(run_phases.ROOT)}: {term}")
    assert offenders == []


def main() -> int:
    tests = [
        test_review_contract,
        test_agent_envelope_review_parsing,
        test_read_only_copy_ignore,
        test_harness_feedback_contract,
        test_phase_prompt_status_contract,
        test_claude_worker_permission_mode_default,
        test_deferable_blocked_reasons,
        test_deferable_verification_failures,
        test_record_deferred_requirement,
        test_atomic_json_write,
        test_status_json_read_retries_during_update,
        test_deferred_requirements_are_collected,
        test_worker_stop_states_become_feedback,
        test_codex_session_preflight_detects_permission_issue,
        test_retry_output_is_concise_by_default,
        test_progress_tracking_contract,
        test_untracked_file_changes_count_as_progress,
        test_legacy_contract_terms_do_not_return,
    ]
    for test in tests:
        test()
        print(f"OK    {test.__name__}")
    print("Workroom Harness self-test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
