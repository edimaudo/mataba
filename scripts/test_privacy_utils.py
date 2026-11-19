#!/usr/bin/env python3
"""Exercise the real TypeScript privacy helpers in Chromium via Python Playwright."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("MATAB_TEST_URL", "http://127.0.0.1:8080")


def wait_for_server(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url + "/api/health", timeout=1.5)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError(f"Mataba FastAPI server is not available at {url}")


def main() -> int:
    build_result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], cwd=ROOT)
    if build_result.returncode:
        return build_result.returncode

    server = None
    if not os.getenv("MATAB_TEST_URL"):
        server = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", "8080",
        ], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    passed = 0
    try:
        wait_for_server(BASE_URL)
        with sync_playwright() as playwright:
            chromium_path = os.getenv("MATAB_CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser")
            browser = playwright.chromium.launch(headless=True, executable_path=chromium_path or None, args=["--no-sandbox"] if chromium_path else None)
            page = browser.new_page()
            page.goto(BASE_URL, wait_until="domcontentloaded")
            actual = page.evaluate("""async () => {
              const privacy = await import('/__tests__/privacy-utils.js');
              const assert = (condition, label) => { if (!condition) throw new Error(label); };
              let count = 0;
              assert(privacy.isValidCanadianSinCandidate('130 692 544') === true, 'valid SIN checksum'); count++;
              assert(privacy.isValidCanadianSinCandidate('123 456 789') === false, 'invalid SIN checksum'); count++;
              assert(privacy.isValidCanadianSinCandidate('130 692 54') === false, 'short SIN rejected'); count++;
              const text = 'Employee Jane Tremblay SIN 130 692 544; email jane.tremblay@example.ca; phone 416-555-0134; salary $125,000.';
              const matches = privacy.collectPatternMatches(text);
              for (const category of ['SIN','EMAIL','PHONE','COMPENSATION']) {
                assert(matches.some((item) => item.category === category), `${category} match`); count++;
              }
              const page = { pageNumber: 1, text };
              const contract = privacy.maskMatchedValues([page], [...matches, { value: 'Jane Tremblay', category: 'NAME' }], 'contract-a1');
              const reference = privacy.maskMatchedValues([page], [{ value: 'Jane Tremblay', category: 'NAME' }], 'reference-b2');
              assert(contract.pages[0].text.includes('[CONTRACTA1_SIN_1]'), 'SIN token namespace'); count++;
              assert(contract.pages[0].text.includes('[CONTRACTA1_EMAIL_1]'), 'email token namespace'); count++;
              assert(contract.pages[0].text.includes('[CONTRACTA1_NAME_1]'), 'name token namespace'); count++;
              assert(contract.tokenMap['[CONTRACTA1_SIN_1]'] === '130 692 544', 'reversible token map'); count++;
              assert(!contract.pages[0].text.includes('jane.tremblay@example.ca'), 'email removed'); count++;
              assert(!contract.pages[0].text.includes('130 692 544'), 'SIN removed'); count++;
              assert(Object.keys(contract.tokenMap).find((key) => key.includes('_NAME_')) !== Object.keys(reference.tokenMap).find((key) => key.includes('_NAME_')), 'separate namespaces prevent collisions'); count++;
              return count;
            }""")
            browser.close()
        print(f"Mataba privacy helpers: {actual} assertions passed in Chromium.")
        return 0
    finally:
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
