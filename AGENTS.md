# Repository Guidelines

## Project Structure & Module Organization

This repository will implement a Python CLI that generates bitrate ladders with convex‑hull selection based on VMAF for user‑specified bitrate‑resolution pairs. All processing is on‑device (no cloud dependencies).

Expected layout:
- `src/`: core library and CLI entry point.
- `tests/`: automated tests.
- `docs/PLAN.md`: project plan and architecture details.
- Optional: `data/` or `assets/` if sample inputs or fixtures are added.

## Build, Test, and Development Commands

All package management and execution must use `uv` only.

## Getting Started Requirements

- Python 3.11+
- `uv`
- `ffmpeg` with `libvmaf` enabled (on macOS, `brew install ffmpeg-full`)

Planned commands (once tooling exists):
- `uv run python -m <module>`: run the CLI locally.
- `uv run pytest`: run the test suite.
- `uv run ruff`: lint the codebase.
- `uv run black`: format code.

## Coding Style & Naming Conventions

- Python 3, 4‑space indentation.
- Prefer type hints for public functions.
- Modules and packages: `snake_case`.
- Classes: `PascalCase`. Functions/variables: `snake_case`.
- Formatting and linting (once configured): `black` and `ruff`, invoked via `uv run`.

## Testing Guidelines

- Framework: `pytest`.
- Test files: `test_*.py` in `tests/`.
- Test functions: `test_*`.
- Run tests with `uv run pytest`.

## Commit & Pull Request Guidelines

- Commit messages follow Conventional Commits (e.g., `feat: add ladder generator`, `fix: handle empty input`).
- PRs should include a clear description, testing notes (commands + results), and link issues when applicable.

## Security & Configuration Notes

- The tool must not call cloud services or require network access at runtime.
- Keep any local configuration in repo‑tracked files; avoid machine‑specific secrets.
