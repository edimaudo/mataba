#!/usr/bin/env python3
"""Run Mataba through one FastAPI development server; rebuild TS assets on change."""
from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_frontend() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], cwd=ROOT, check=True)


def watch_frontend(stop_event: threading.Event) -> None:
    try:
        from watchfiles import watch
    except ImportError:
        print("Install requirements-dev.txt to enable frontend auto-rebuild (watchfiles).")
        return

    watch_paths = [ROOT / "frontend" / "src", ROOT / "frontend" / "public", ROOT / "frontend" / "index.html"]
    try:
        for _changes in watch(*watch_paths, debounce=500, stop_event=stop_event):
            if stop_event.is_set():
                break
            try:
                build_frontend()
                print("Frontend refreshed; FastAPI continues serving the same origin.")
            except subprocess.CalledProcessError:
                print("Frontend build failed; the previous built files remain available.", file=sys.stderr)
    except KeyboardInterrupt:
        stop_event.set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Mataba with one Python/FastAPI application server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-reload", action="store_true", help="Disable Python backend auto-reload.")
    args = parser.parse_args()

    build_frontend()

    stop_event = threading.Event()
    watcher = threading.Thread(target=watch_frontend, args=(stop_event,), daemon=True)
    watcher.start()

    command = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", args.host, "--port", str(args.port),
    ]
    if not args.no_reload:
        command.extend(["--reload", "--reload-dir", str(ROOT / "app")])

    print(f"Mataba is running at http://{args.host}:{args.port}")
    print("One server: Python + FastAPI. Press Ctrl+C to stop.")
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        return process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        stop_event.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        watcher.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
