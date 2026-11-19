#!/usr/bin/env python3
"""Compile all browser TypeScript entry points using the native esbuild CLI."""
from build import build

if __name__ == "__main__":
    build()
    print("Frontend TypeScript transpilation and bundle validation passed.")
