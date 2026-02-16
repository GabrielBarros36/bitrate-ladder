# bitrate-ladder

CLI for generating bitrate ladders from explicit bitrate-resolution points using FFmpeg + VMAF and upper convex hull selection.

## Getting Started Requirements

- Python 3.11+
- `uv`
- `ffmpeg` with `libvmaf` enabled (on macOS, `brew install ffmpeg-full`)

## Quick Start

```bash
uv run python -m bitrate_ladder --config path/to/config.json
```

Required config fields:
- `input.source_path`
- `ladder.points` (list of `{ bitrate_kbps, width, height, codec }`)

Important for multi-resolution ladders:
- Set `vmaf.evaluation_resolution` in config (for example, `"1920x1080"`), or pass `--evaluation-resolution 1920x1080`.

Keep encode artifacts for later visual comparison:

```bash
uv run python -m bitrate_ladder --config path/to/config.json --keep-temp
```

## GUI Compare App

Launch the local browser GUI from an existing report:

```bash
uv run python -m bitrate_ladder compare --report out/report.json
```

Useful options:
- `--encodes-dir <path>`: fallback for missing `encode_path` entries.
- `--vmaf-dir <path>`: fallback for missing `vmaf_log_path` entries.
- `--cache-dir <path>`: proxy cache location.
- `--clear-cache`: clear existing proxy cache before startup.
- `--no-open-browser`: do not auto-open a browser tab.

Install compare-mode Python dependencies:

```bash
uv sync --extra compare
```

More command examples:
- `examples/EXAMPLE_USAGES.md`

## Docs

- GUI compare module: `docs/GUI_COMPARE.md`
- Examples overview: `examples/README.md`
- Command examples: `examples/EXAMPLE_USAGES.md`

## Development

Install dev dependencies:

```bash
uv sync --extra dev --extra yaml
```

Run checks:

```bash
uv run ruff check .
uv run black --check .
uv run mypy src/bitrate_ladder
uv run pytest
```

Enable automatic lint/format/type checks before commits:

```bash
uv run pre-commit install
```

Frontend tooling for the compare web app (optional, uses npm):

```bash
cd web/compare
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```
