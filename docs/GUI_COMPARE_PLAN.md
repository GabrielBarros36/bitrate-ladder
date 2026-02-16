# GUI Compare Module Plan

## Summary

Add a separate cross-platform GUI module (local web app) to compare retained encodes from a ladder report. The GUI supports:
- Tile mode: up to 4 synchronized videos.
- Wipe mode: 2 videos with draggable vertical splitter.
- Frame-accurate preprocessing via cached aligned proxies.
- VMAF timeline overlays (A, B, and delta).

## CLI Surface

New command:
- `uv run python -m bitrate_ladder compare --report <report.json>`

Options:
- `--host` (default `127.0.0.1`)
- `--port` (default `8765`)
- `--open-browser/--no-open-browser`
- `--encodes-dir` fallback encode directory
- `--vmaf-dir` fallback VMAF log directory
- `--cache-dir` compare proxy cache directory
- `--clear-cache` clear cache before startup

## Session and Input Model

- Session is report-driven plus source file.
- Compare sources are report points and/or source.
- Fail-fast for missing source/encode/VMAF paths with a repair panel.
- Path repair is session-local via API.

## Backend Design

Package: `src/bitrate_ladder/compare/`
- `cli.py`: compare subcommand and server startup.
- `session.py`: report loading, path resolution, issue detection/repair.
- `preprocess.py`: aligned proxy creation and cache lifecycle.
- `server.py`: local API + static UI serving.
- `models.py`: internal compare/session models.

API endpoints:
- `GET /api/session`
- `POST /api/session/repair`
- `POST /api/compare/prepare`
- `GET /api/media/{asset_token}`
- `GET /api/vmaf/{point_id}`
- `POST /api/cache/clear`

## Frontend Design

- Local browser app served by Python backend.
- Modes: `tile`, `wipe`.
- Shared controls: play/pause, seek, frame-step, speed.
- Keyboard shortcuts: `Space`, `ArrowLeft`, `ArrowRight`, `,`, `.`, `1`, `2`.
- VMAF panel displays per-frame curves and delta when both sides are report points.

## Frame-Accurate Preprocessing

- On-demand per selected comparison set.
- Normalize to shared FPS and resolution, encode proxy as H.264 MP4.
- Trim to common duration.
- Deterministic cache key uses input fingerprints + normalization parameters.
- Cache stored under compare cache dir until explicit cleanup.

## Storage Policy

- Ladder generation still controls artifact retention via `keep_temp`.
- Compare module expects retained files or repaired paths.

## Testing Strategy

Unit/API tests cover:
- Session parsing, fallback path reconstruction, and issue detection.
- Repair workflow updates.
- Cache key determinism and preprocessing validation.
- Compare CLI dispatch.

Integration tests can be added behind ffmpeg/libvmaf markers for full proxy generation + playback preparation.

## Tooling and Docs

- Update repository guidelines to allow Node/npm for GUI tooling.
- Keep Python checks via `uv` and define npm lint/typecheck/test/build process.
- Document GUI command usage and behavior in README.
