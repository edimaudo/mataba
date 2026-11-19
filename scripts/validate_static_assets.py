#!/usr/bin/env python3
"""Check that Mataba's served application assets are present and use native JavaScript."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"

required = [
    TEMPLATES / "index.html",
    TEMPLATES / "404.html",
    STATIC / "config.js",
    STATIC / "css" / "styles.css",
    STATIC / "js" / "main.js",
    STATIC / "js" / "lib" / "privacy-utils.js",
]
missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
if missing:
    raise SystemExit("Missing application assets: " + ", ".join(missing))

if list(ROOT.rglob("*.ts")) or list(ROOT.rglob("*.tsx")):
    raise SystemExit("TypeScript files are not permitted in this Python/JavaScript application.")
if (ROOT / "frontend").exists() or (ROOT / "package.json").exists():
    raise SystemExit("A separate frontend application or Node package manifest remains in the project.")

html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
if 'type="module" src="/js/main.js"' not in html:
    raise SystemExit("The HTML entry page does not load the native JavaScript application module.")
if re.search(r'(?:src|href)="/(?:app\.js|styles\.css|assets/)', html):
    raise SystemExit("The HTML entry page still references generated build output.")

print("Mataba static application validation passed. No TypeScript or Node build is required.")
