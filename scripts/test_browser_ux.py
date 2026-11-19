#!/usr/bin/env python3
"""Browser UX and axe-core checks using Python Playwright and the FastAPI server."""
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
AXE_SCRIPT_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js"


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

    server = None
    if not os.getenv("MATAB_TEST_URL"):
        server = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", "8080",
        ], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    passed: list[str] = []
    failures: list[str] = []

    def record(name: str, condition: bool, detail: str = "") -> None:
        (passed if condition else failures).append(name if condition else f"{name}: {detail}".rstrip())

    try:
        wait_for_server(BASE_URL)
        with sync_playwright() as playwright:
            chromium_path = os.getenv("MATAB_CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser")
            browser = playwright.chromium.launch(headless=True, executable_path=chromium_path or None, args=["--no-sandbox"] if chromium_path else None)
            context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            page = context.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, content_type="text/css", body=""))
            page.route("https://fonts.gstatic.com/**", lambda route: route.abort())
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.locator(".local-entry").wait_for(state="visible")
            page.add_script_tag(url=AXE_SCRIPT_URL)

            axe_tags = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]

            def axe_scan(label: str) -> None:
                result = page.evaluate("""async (tags) => {
                  const result = await window.axe.run(document, { runOnly: tags });
                  return result.violations.map((item) => `${item.id} (${item.impact}, ${item.nodes.length} node(s))`);
                }""", axe_tags)
                record(f"{label}: no WCAG 2.2 AA violations", len(result) == 0, "; ".join(result))

            axe_scan("Authentication/local-preview screen")
            record("Skip link is available before entering the application", page.locator("#skip-to-main").count() == 1)
            record("Application root is not incorrectly marked as a live region", page.locator("#app").get_attribute("aria-live") is None)
            page.locator(".local-entry").click()
            page.locator(".app-shell").wait_for(state="visible")
            record("Local preview opens the application shell", page.locator(".app-shell").count() == 1)
            record("A primary page heading is present", page.locator("main h1").count() == 1)
            record("Main landmark has programmatic focus target", page.locator("main#main-content[tabindex='-1']").count() == 1)
            record("Rendered buttons have explicit types", page.locator("button:not([type])").count() == 0)
            fields_named = page.locator("input:not([type='hidden']), select, textarea").evaluate_all("fields => fields.every(field => Boolean(field.getAttribute('aria-label') || field.getAttribute('aria-labelledby') || field.labels?.length))")
            record("Visible form fields have accessible names", fields_named)

            page.locator("#skip-to-main").focus()
            page.keyboard.press("Enter")
            record("Skip link transfers focus to main content", page.evaluate("document.activeElement?.id === 'main-content'"))

            sidebar = page.locator("#primary-sidebar")
            menu = page.locator(".mobile-menu")
            menu.click()
            record("Closed mobile sidebar is inert", sidebar.evaluate("element => element.inert"))
            record("Open mobile navigation is a labelled modal dialog", sidebar.get_attribute("role") == "dialog" and sidebar.get_attribute("aria-modal") == "true" and bool(sidebar.get_attribute("aria-label")))
            record("Background content is inert while drawer is open", page.locator(".main-area").evaluate("element => element.inert && element.getAttribute('aria-hidden') === 'true'"))
            record("Opening drawer moves focus inside it", sidebar.evaluate("element => element.contains(document.activeElement)"))
            page.keyboard.press("Shift+Tab")
            record("Mobile drawer traps reverse keyboard focus", sidebar.evaluate("element => element.contains(document.activeElement)"))
            page.keyboard.press("Tab")
            record("Mobile drawer wraps forward keyboard focus", sidebar.evaluate("element => element.contains(document.activeElement)"))
            page.keyboard.press("Escape")
            record("Escape closes drawer and restores focus", menu.get_attribute("aria-expanded") == "false" and menu.evaluate("element => document.activeElement === element"))
            record("Closed drawer is inert and hidden from assistive technology", sidebar.evaluate("element => element.inert && element.getAttribute('aria-hidden') === 'true'"))

            menu.click()
            sidebar.locator("[data-action='navigate'][data-section='settings']").click()
            page.locator("[data-action='set-theme']").wait_for(state="visible")
            record("Navigation moves focus to destination heading", page.evaluate("document.activeElement?.matches('#main-content h1')"))
            page.locator("[data-action='set-theme'][data-value='dark']").click()
            record("Dark theme updates document state", page.locator("html").get_attribute("data-theme") == "dark")
            record("Theme control retains keyboard focus", page.evaluate("document.activeElement?.getAttribute('data-value') === 'dark'"))
            page.locator("[data-action='set-font'][data-value='large']").click()
            record("Large typography sets 1.25em root scale", page.locator("html").evaluate("element => getComputedStyle(element).fontSize") == "20px")
            record("Font control retains keyboard focus", page.evaluate("document.activeElement?.getAttribute('data-value') === 'large'"))
            page.locator("[data-action='toggle-language']").click()
            record("French selection updates document language", page.locator("html").get_attribute("lang") == "fr-CA")
            record("French settings heading is translated", (page.locator("main h1").text_content() or "").strip() == "Paramètres")
            record("Language control retains keyboard focus", page.evaluate("document.activeElement?.matches('[data-action=toggle-language]')"))
            record("Segmented controls expose pressed state", page.locator(".segmented-control button").evaluate_all("elements => elements.length > 0 && elements.every(element => element.hasAttribute('aria-pressed'))"))
            axe_scan("French settings, dark theme and large typography")

            page.locator("[data-action='set-font'][data-value='small']").click()
            record("Small typography sets 0.75em root scale", page.locator("html").evaluate("element => getComputedStyle(element).fontSize") == "12px")
            page.locator("[data-action='set-font'][data-value='medium']").click()
            record("Medium typography sets 1em root scale", page.locator("html").evaluate("element => getComputedStyle(element).fontSize") == "16px")
            page.locator("[data-action='set-theme'][data-value='light']").click()
            record("Light theme restores document state", page.locator("html").get_attribute("data-theme") == "light")
            axe_scan("French settings, light theme and medium typography")

            for section in ["new", "references", "library", "recent"]:
                if menu.get_attribute("aria-expanded") != "true":
                    menu.click()
                sidebar.locator(f"[data-action='navigate'][data-section='{section}']").click()
                page.locator("main h1").wait_for(state="visible")
                fields_named = page.locator("input:not([type='hidden']), select, textarea").evaluate_all("fields => fields.every(field => Boolean(field.getAttribute('aria-label') || field.getAttribute('aria-labelledby') || field.labels?.length))")
                record(f"{section} page: all form fields have accessible names", fields_named)
                record(f"{section} page: no missing button types", page.locator("button:not([type])").count() == 0)
                axe_scan(f"{section} page on mobile")

            page.set_viewport_size({"width": 320, "height": 780})
            page.wait_for_timeout(100)
            overflow = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            dimensions = page.evaluate("`${document.documentElement.scrollWidth}px document / ${window.innerWidth}px viewport`")
            record("320px viewport has no document-level horizontal overflow", overflow, dimensions)
            record("320px layout preserves visible main heading", page.locator("main h1").is_visible())

            page.set_viewport_size({"width": 850, "height": 900})
            page.wait_for_timeout(100)
            record("850px breakpoint uses mobile sidebar behavior", sidebar.evaluate("element => element.inert"))
            page.set_viewport_size({"width": 851, "height": 900})
            page.wait_for_timeout(100)
            record("851px breakpoint restores desktop sidebar semantics", sidebar.get_attribute("role") == "complementary" and not sidebar.evaluate("element => element.inert"))
            record("Desktop width has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
            axe_scan("Desktop recent reviews page")
            record("No uncaught JavaScript exceptions occurred during UX flow", len(page_errors) == 0, " | ".join(page_errors))

            context.close()
            browser.close()

        print(f"Mataba browser UX checks: {len(passed)} passed, {len(failures)} failed.")
        for item in passed:
            print(f"PASS {item}")
        for item in failures:
            print(f"FAIL {item}", file=sys.stderr)
        return 1 if failures else 0
    finally:
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
