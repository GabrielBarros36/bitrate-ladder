#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Ensure a stable local environment for git hooks.
uv sync --extra dev --extra yaml
uv run pre-commit install --hook-type pre-commit --hook-type pre-push

echo "Installed git hooks: pre-commit and pre-push"
