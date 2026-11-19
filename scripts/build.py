#!/usr/bin/env python3
"""Build Mataba's browser TypeScript bundle and static assets using Python orchestration.

esbuild itself is a standalone native executable. It is invoked directly; no Node
application server or JavaScript build wrapper is involved.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DIST = ROOT / "public"


def find_esbuild() -> Path:
    system = platform.system().lower()
    machine = platform.machine().lower()
    platform_name = {
        ("linux", "x86_64"): "linux-x64",
        ("linux", "amd64"): "linux-x64",
        ("linux", "aarch64"): "linux-arm64",
        ("linux", "arm64"): "linux-arm64",
        ("darwin", "x86_64"): "darwin-x64",
        ("darwin", "arm64"): "darwin-arm64",
        ("windows", "amd64"): "win32-x64",
        ("windows", "x86_64"): "win32-x64",
        ("windows", "arm64"): "win32-arm64",
    }.get((system, machine))

    candidates: list[Path] = []
    if platform_name:
        executable = "esbuild.exe" if system == "windows" else "esbuild"
        candidates.append(FRONTEND / "node_modules" / "@esbuild" / platform_name / "bin" / executable)
    on_path = shutil.which("esbuild")
    if on_path:
        candidates.append(Path(on_path))

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise RuntimeError(
        "The standalone esbuild compiler was not found. Install the browser dependencies once with "
        "`npm install --prefix frontend`, then run this Python build script again. "
        "Node/npm are used only to retrieve browser libraries and the native compiler; they do not run Mataba."
    )


def run_esbuild(binary: Path, args: list[str]) -> None:
    command = [str(binary), *args]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"esbuild failed with exit code {result.returncode}")


def build() -> None:
    binary = find_esbuild()
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    (DIST / "__tests__").mkdir(parents=True)

    run_esbuild(binary, [
        str(FRONTEND / "src" / "main.ts"),
        "--bundle", "--platform=browser", "--format=esm", "--target=es2022",
        "--sourcemap", "--outfile=" + str(DIST / "app.js"),
    ])
    # Build the pure privacy module separately so the Python Playwright test can
    # exercise the actual TypeScript implementation in a real browser runtime.
    run_esbuild(binary, [
        str(FRONTEND / "src" / "lib" / "privacy-utils.ts"),
        "--bundle", "--platform=browser", "--format=esm", "--target=es2022",
        "--outfile=" + str(DIST / "__tests__" / "privacy-utils.js"),
    ])

    shutil.copy2(FRONTEND / "index.html", DIST / "index.html")
    shutil.copy2(FRONTEND / "404.html", DIST / "404.html")
    shutil.copy2(FRONTEND / "src" / "styles.css", DIST / "styles.css")
    shutil.copy2(FRONTEND / "public" / "config.js", DIST / "config.js")

    # PDF.js ships an ES module worker with an .mjs suffix. It is a vendor asset,
    # not application code. Copy it as .js so Mataba's own source tree contains
    # no custom .mjs files; module workers are selected by PDF.js at runtime.
    worker_source = FRONTEND / "node_modules" / "pdfjs-dist" / "build" / "pdf.worker.min.mjs"
    if worker_source.is_file():
        shutil.copy2(worker_source, DIST / "assets" / "pdf.worker.min.js")
    else:
        raise RuntimeError(f"PDF.js worker asset missing: {worker_source}. Reinstall frontend dependencies.")

    print(f"Mataba frontend built successfully: {DIST.relative_to(ROOT)}")
    print(f"Compiler: {binary}")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
