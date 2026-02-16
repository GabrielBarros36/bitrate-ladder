# Repository Guidelines

## Project Structure & Module Organization

This repository implements a Python CLI that generates bitrate ladders with convex-hull selection based on VMAF for user-specified bitrate-resolution-codec points, plus a local GUI compare app for visual side-by-side analysis. All processing is on-device (no cloud dependencies).

Current architecture:
- `src/bitrate_ladder/cli.py`: CLI argument parsing, pipeline orchestration, success/error messaging.
- `src/bitrate_ladder/config.py`: JSON/YAML config loading, validation, defaults.
- `src/bitrate_ladder/encode.py`: FFmpeg encode invocation per ladder point.
- `src/bitrate_ladder/vmaf.py`: FFmpeg/libvmaf execution and log handling.
- `src/bitrate_ladder/metrics.py`: parsing VMAF JSON into summary metrics.
- `src/bitrate_ladder/ladder.py`: RD point handling, upper hull selection, BD-rate helper.
- `src/bitrate_ladder/report.py`: report assembly + JSON write helpers.
- `src/bitrate_ladder/plots.py`: plotting utilities (per-codec overlays and all-codecs overlay).
- `src/bitrate_ladder/compare/cli.py`: compare subcommand argument parsing and app startup.
- `src/bitrate_ladder/compare/server.py`: local API + static UI serving for the compare app.
- `src/bitrate_ladder/compare/session.py`: report/session loading, validation, and repair handling.
- `src/bitrate_ladder/compare/preprocess.py`: aligned proxy generation and compare cache management.
- `src/bitrate_ladder/compare/models.py`: compare/session dataclasses and internal models.
- Multi-resolution evaluation rule: when ladder points span multiple resolutions, a shared VMAF evaluation resolution is required (`vmaf.evaluation_resolution` or CLI `--evaluation-resolution`).

Current file layout:
- `README.md`: concise usage + requirements.
- `docs/PLAN.md`: original project plan.
- `docs/GUI_COMPARE.md`: GUI compare usage and troubleshooting.
- `docs/GUI_COMPARE_PLAN.md`: compare module implementation plan.
- `src/bitrate_ladder/`: package source.
- `tests/`: unit + integration tests.
- `examples/`: runnable example configs and usage docs.
- `web/compare/`: frontend tooling for compare UI (npm-based).
- `pyproject.toml` and `uv.lock`: project/dependency configuration.

## Build, Test, and Development Commands

Python package management and execution must use `uv`.
For the compare frontend under `web/compare`, npm is allowed and required for linting/testing/building.

## Getting Started Requirements

- Python 3.11+
- `uv`
- `ffmpeg` with `libvmaf` enabled (on macOS, `brew install ffmpeg-full`)
- Node.js + `npm` (only for `web/compare` frontend development checks)

Primary commands:
- `uv run python -m bitrate_ladder --config <config-path>`: run the CLI.
- `uv run python -m bitrate_ladder --config <config-path> --evaluation-resolution <width>x<height>`: required override when config does not define `vmaf.evaluation_resolution` for multi-resolution ladders.
- `uv run python -m bitrate_ladder compare --report <report-path>`: launch local compare GUI app.
- `uv sync --extra compare`: install compare-mode Python dependencies.
- `uv run pytest`: run the test suite.
- `uv run ruff check .`: lint the codebase.
- `uv run black`: format code.
- `cd web/compare && npm install`: install frontend dependencies.
- `cd web/compare && npm run lint && npm run typecheck && npm run test && npm run build`: validate GUI frontend.

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
- Commit after every change in small, coherent increments (avoid very large mixed commits).
- PRs should include a clear description, testing notes (commands + results), and link issues when applicable.

## Security & Configuration Notes

- The tool must not call cloud services or require network access at runtime.
- Keep any local configuration in repo‑tracked files; avoid machine‑specific secrets.
