# Examples Folder

This folder contains runnable sample configs and usage references for `bitrate-ladder`.

## Contents

- `examples/EXAMPLE_USAGES.md`: command-oriented usage patterns.
- `examples/configs/basic_h264.json`: simple H.264, same-resolution ladder.
- `examples/configs/multi_resolution_codecs.json`: mixed resolution and mixed codec run.
- `examples/configs/compare_ready.json`: GUI-oriented config that keeps encode artifacts.
- `examples/configs/minimal_av1.json`: small AV1-only config.

## Important Input Note

These configs currently reference:

- `input.source_path`: `9910331-uhd_3840_2160_30fps.mp4`

If that file is not present in your local repository root, edit `input.source_path` in each config to point to a valid local video.

## Quick Run Commands

### Basic run

```bash
uv run python -m bitrate_ladder --config examples/configs/basic_h264.json
```

### Multi-resolution mixed codecs

```bash
uv run python -m bitrate_ladder --config examples/configs/multi_resolution_codecs.json
```

### Compare-ready generation (keeps artifacts)

```bash
uv run python -m bitrate_ladder --config examples/configs/compare_ready.json
```

### Launch GUI from compare-ready output

```bash
uv sync --extra compare
uv run python -m bitrate_ladder compare --report out/examples/compare_ready_report.json
```

## Outputs Used by the Examples

- Reports and plots are written to `out/examples/...`.
- Compare-ready intermediate files are written to `out/examples/compare_work/...`.
- GUI proxy cache defaults under `out/examples/compare_work/compare_cache/...`.
