from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Sequence

from .preprocess import clear_cache_dir
from .session import SessionError, load_session


class CompareCliError(RuntimeError):
    """Raised when compare CLI arguments or runtime setup are invalid."""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bitrate-ladder compare",
        description="Launch the local GUI for side-by-side encode comparison.",
    )
    parser.add_argument("--report", required=True, help="Path to the generated report JSON")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the compare web server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the compare web server (default: 8765)",
    )
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Open a browser tab automatically (default: true)",
    )
    parser.add_argument(
        "--encodes-dir",
        default=None,
        help="Fallback directory for encode files when encode_path is missing in report points",
    )
    parser.add_argument(
        "--vmaf-dir",
        default=None,
        help="Fallback directory for vmaf logs when vmaf_log_path is missing in report points",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for cached aligned compare proxies",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        default=False,
        help="Clear compare proxy cache before starting",
    )
    parser.add_argument(
        "--ffmpeg-bin",
        default="ffmpeg",
        help="FFmpeg binary path for preprocessing (default: ffmpeg)",
    )
    parser.add_argument(
        "--ffprobe-bin",
        default="ffprobe",
        help="ffprobe binary path for preprocessing (default: ffprobe)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.port <= 0 or args.port > 65535:
        print("error: --port must be between 1 and 65535", file=sys.stderr)
        return 1

    try:
        import uvicorn
    except ImportError:
        print(
            "error: compare mode dependencies are not installed. Run `uv sync --extra compare`.",
            file=sys.stderr,
        )
        return 1

    try:
        from .server import create_app
    except ImportError:
        print(
            "error: compare mode dependencies are not installed. Run `uv sync --extra compare`.",
            file=sys.stderr,
        )
        return 1

    try:
        session = load_session(
            Path(args.report),
            encodes_dir=Path(args.encodes_dir).resolve() if args.encodes_dir else None,
            vmaf_dir=Path(args.vmaf_dir).resolve() if args.vmaf_dir else None,
            cache_dir=Path(args.cache_dir).resolve() if args.cache_dir else None,
        )
    except SessionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    session.cache_dir.mkdir(parents=True, exist_ok=True)
    if args.clear_cache:
        clear_cache_dir(session.cache_dir)
        session.cache_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(
        session,
        ffmpeg_bin=args.ffmpeg_bin,
        ffprobe_bin=args.ffprobe_bin,
    )

    url = f"http://{args.host}:{args.port}"
    issue_count = len(session.issues)
    if issue_count:
        print(f"Compare session loaded with {issue_count} unresolved path issue(s).")
        print("Use the Repair panel in the UI before preparing comparisons.")

    print(f"Starting compare GUI at {url}")
    if args.open_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=args.host,
            port=args.port,
            log_level="info",
        )
    )
    server.run()
    return 0


def _open_browser(url: str) -> None:
    time.sleep(0.75)
    webbrowser.open(url)
