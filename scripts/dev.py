#!/usr/bin/env python3
"""Run Mataba with its single Python/FastAPI application server."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Mataba with one Python/FastAPI server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-reload", action="store_true", help="Disable Python auto-reload.")
    args = parser.parse_args()

    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)]
    if not args.no_reload:
        command.extend(["--reload", "--reload-dir", str(ROOT / "app")])

    print(f"Mataba is running at http://{args.host}:{args.port}")
    print("Python + FastAPI only. No frontend compilation or Node tooling.")
    try:
        return subprocess.call(command, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
