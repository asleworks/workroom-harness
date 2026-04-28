#!/usr/bin/env python3

import shutil
from pathlib import Path


WORKROOM_DIR = Path(__file__).resolve().parent.parent
SOURCE_ROOT = WORKROOM_DIR.parent

CORE_DIRS = [".workroom"]

SKILL_DIRS = {
    "codex": [".agents"],
    "claude": [".claude"],
    "both": [".agents", ".claude"],
}

GITIGNORE_MARKER = "# workroom-harness"
PROJECT_STATE_PATHS = (
    "AGENTS.md",
    "docs/",
    "phases/",
    "scripts/verify.sh",
)


def is_project_state(rel_path: Path) -> bool:
    rel = rel_path.as_posix()
    return any(rel == item.rstrip("/") or rel.startswith(item) for item in PROJECT_STATE_PATHS)


def copy_file(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> str:
    existed = dst.exists()
    if existed and not overwrite:
        return "skip"

    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if dst.suffix in {".py", ".sh"}:
            dst.chmod(dst.stat().st_mode | 0o755)

    return "overwrite" if existed else "write"


def copy_tree_files(
    src_dir: Path,
    dst_dir: Path,
    overwrite: bool,
    dry_run: bool,
    excludes: set[str] | None = None,
) -> list[tuple[str, Path]]:
    excludes = excludes or set()
    results = []
    for src in src_dir.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(src_dir)
        if (
            rel.as_posix() in excludes
            or "__pycache__" in src.parts
            or src.suffix in {".pyc", ".log"}
            or src.name in {".DS_Store", "context.md"}
        ):
            continue
        dst = dst_dir / rel
        effective_overwrite = overwrite and not is_project_state(rel)
        action = copy_file(src, dst, effective_overwrite, dry_run)
        results.append((action, dst))
    return results


def install_gitignore(target: Path, dry_run: bool) -> list[tuple[str, Path]]:
    path = target / ".gitignore"
    ignore_lines = [
        ".workroom/phases/**/*.log",
        ".workroom/phases/**/*.log.final",
        ".workroom/phases/**/context.md",
        ".workroom/reviews/*.log",
        ".workroom/reviews/*.log.final",
    ]
    section = f"""

{GITIGNORE_MARKER}
{chr(10).join(ignore_lines)}
"""

    if not path.exists():
        if not dry_run:
            path.write_text(section.lstrip(), encoding="utf-8")
        return [("write", path)]

    text = path.read_text(encoding="utf-8")
    if GITIGNORE_MARKER in text:
        missing = [line for line in ignore_lines if line not in text]
        if not missing:
            return [("skip", path)]
        if not dry_run:
            path.write_text(text.rstrip() + "\n" + "\n".join(missing) + "\n", encoding="utf-8")
        return [("append", path)]

    if not dry_run:
        path.write_text(text.rstrip() + section + "\n", encoding="utf-8")
    return [("append", path)]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Install Workroom Harness into an existing project.")
    parser.add_argument("target", nargs="?", default=".", help="Target project directory")
    parser.add_argument(
        "--agent",
        choices=["codex", "claude", "both"],
        default="both",
        help="Which agent skill directories to install",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite harness-owned files while preserving project docs, phases, AGENTS.md, and verify.sh",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be installed")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"ERROR: target directory does not exist: {target}")
        return 1

    if target == SOURCE_ROOT:
        print("ERROR: target is the Workroom Harness repository itself")
        return 1

    print(f"Installing Workroom Harness into {target}")
    if args.dry_run:
        print("Dry run: no files will be changed")

    results: list[tuple[str, Path]] = []
    results.extend(install_gitignore(target, args.dry_run))

    for dirname in CORE_DIRS:
        results.extend(
            copy_tree_files(
                SOURCE_ROOT / dirname,
                target / dirname,
                args.overwrite,
                args.dry_run,
            )
        )

    for dirname in SKILL_DIRS[args.agent]:
        results.extend(
            copy_tree_files(
                SOURCE_ROOT / dirname,
                target / dirname,
                args.overwrite,
                args.dry_run,
            )
        )

    for action, path in results:
        print(f"{action:9} {path.relative_to(target)}")

    print()
    print("Next steps:")
    print("1. Run python3 .workroom/scripts/doctor.py from the target project.")
    print("2. Run $workroom-plan in Codex or /workroom-plan in Claude to fill docs.")
    print("3. Edit .workroom/scripts/verify.sh so it runs your real checks.")
    print("4. Use $workroom-phase and $workroom-harness in Codex, or /workroom-phase and /workroom-harness in Claude.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
