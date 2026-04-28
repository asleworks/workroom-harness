#!/usr/bin/env bash

set -euo pipefail

REPO="${WORKROOM_HARNESS_REPO:-asleworks/workroom-harness}"
REF="${WORKROOM_HARNESS_REF:-main}"
TARGET="."
OVERWRITE=""
DRY_RUN=""

usage() {
  cat <<EOF
Install Workroom Harness for Claude Code into an existing project.

Usage:
  curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-claude.sh | bash
  curl -fsSL https://raw.githubusercontent.com/asleworks/workroom-harness/main/.workroom/scripts/install-claude.sh | bash -s -- /path/to/project

Options:
  --overwrite  Overwrite harness-owned files while preserving project state.
  --dry-run    Show what would change.

Environment:
  WORKROOM_HARNESS_REPO  GitHub repo, default: asleworks/workroom-harness
  WORKROOM_HARNESS_REF   Branch, tag, or ref, default: main
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --overwrite)
      OVERWRITE="--overwrite"
      shift
      ;;
    --dry-run)
      DRY_RUN="--dry-run"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      TARGET="$1"
      shift
      ;;
  esac
done

command -v curl >/dev/null 2>&1 || {
  echo "ERROR: curl is required" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 is required" >&2
  exit 1
}

command -v tar >/dev/null 2>&1 || {
  echo "ERROR: tar is required" >&2
  exit 1
}

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

ARCHIVE="$TMP_DIR/workroom-harness.tar.gz"
URL="https://github.com/${REPO}/archive/${REF}.tar.gz"

echo "Downloading Workroom Harness from ${REPO}@${REF}"
curl -fsSL "$URL" -o "$ARCHIVE"
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

SOURCE_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"

python3 "$SOURCE_DIR/.workroom/scripts/install.py" "$TARGET" --agent claude $OVERWRITE $DRY_RUN
