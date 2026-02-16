#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[check-all] Running Python checks"
uv run --with ruff ruff check .
uv run --with black black --check .
uv run --with mypy --with types-PyYAML mypy src/bitrate_ladder
uv run --with pytest pytest

if [[ "${SKIP_GUI_CHECKS:-0}" == "1" ]]; then
  echo "[check-all] SKIP_GUI_CHECKS=1 set; skipping GUI checks"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[check-all] npm is required for GUI checks but was not found in PATH" >&2
  exit 1
fi

if [[ ! -d "web/compare/node_modules" ]]; then
  echo "[check-all] Installing GUI dependencies"
  npm --prefix web/compare install
fi

echo "[check-all] Running GUI checks"
npm --prefix web/compare run lint
npm --prefix web/compare run typecheck
npm --prefix web/compare run test
npm --prefix web/compare run build

echo "[check-all] All checks passed"
