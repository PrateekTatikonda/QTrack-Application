#!/usr/bin/env python3
"""
QTrack backend server runner.

    python run_server.py           # development (auto-reload)
    python run_server.py --prod    # production-style (no reload)
"""

import argparse
import os
import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the QTrack FastAPI server")
    parser.add_argument("--prod", action="store_true", help="disable auto-reload")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--log-level", default="info")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reload = not args.prod

    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))

    print(f"Starting QTrack backend ({'development, auto-reload' if reload else 'production'})")
    print(f"  API:  http://localhost:{args.port}")
    print(f"  Docs: http://localhost:{args.port}/docs")
    print("  Press Ctrl+C to stop")

    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=reload,
            reload_dirs=[str(BACKEND_DIR / "app")] if reload else None,
            log_level=args.log_level,
            access_log=True,
            # Long-lived SSE connections would otherwise block shutdown on Ctrl+C.
            timeout_graceful_shutdown=5,
        )
    except KeyboardInterrupt:
        print("\nQTrack backend stopped.")


if __name__ == "__main__":
    main()
