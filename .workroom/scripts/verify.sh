#!/usr/bin/env bash

set -euo pipefail

echo "Running Workroom Harness verification..."

if [ -f "package.json" ]; then
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "package.json found, but node or npm is not installed."
    exit 1
  fi

  has_script() {
    node -e "const p=require('./package.json'); process.exit(p.scripts && p.scripts[process.argv[1]] ? 0 : 1)" "$1"
  }

  for script in lint typecheck test build; do
    if has_script "$script"; then
      npm run "$script"
    fi
  done
else
  echo "No package.json found. Skipping npm checks."
fi

echo "Verification complete."
