#!/usr/bin/env python3
"""Browser UX and axe-core checks for the direct-entry Mataba app."""
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
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8080"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    passed: list[str] = []
    failures: list[str] = []

    def record(name: str, condition: bool, detail: str = "") -> None:
        (passed if condition else failures).append(name if condition else f"{name}: {detail}".rstrip())

    try:
        wait_for_server(BASE_URL)
        with sync_playwright() as playwright:
            chromium_path = os.getenv("MATAB_CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser")
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=chromium_path or None,
                args=["--no-sandbox"] if chromium_path else None,
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
            page = context.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, content_type="text/css", body=""))
            page.route("https://fonts.gstatic.com/**", lambda route: route.abort())

            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.locator(".landing-card").first.wait_for(state="visible")
            page.add_script_tag(url=AXE_SCRIPT_URL)
            axe_tags = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]

            def axe_scan(label: str) -> None:
                result = page.evaluate(
                    """async (tags) => {
                      const result = await window.axe.run(document, { runOnly: tags });
                      return result.violations.map(item => `${item.id} (${item.impact}, ${item.nodes.length} node(s))`);
                    }""",
                    axe_tags,
                )
                record(f"{label}: no WCAG 2.2 AA violations", len(result) == 0, "; ".join(result))

            record("Landing page has one primary heading", page.locator("main h1").count() == 1)
            record("Landing header has no secondary navigation", page.locator(".site-header .primary-nav").count() == 0)
            record("Landing header has no sign-in control", page.get_by_text("Sign in", exact=True).count() == 0)
            record("Landing page has no footer", page.locator("footer").count() == 0)
            record("Landing page has two information cards", page.locator(".landing-card").count() == 2)
            card_dimensions = page.locator(".landing-card").evaluate_all("items => items.map(item => Math.round(item.getBoundingClientRect().height))")
            record("Landing cards have equal heights", len(card_dimensions) == 2 and card_dimensions[0] == card_dimensions[1], str(card_dimensions))
            card_columns = page.locator(".landing-cards").evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length")
            record("Landing information cards display side by side on desktop", card_columns == 2, str(card_columns))
            record("Start a review opens the app", page.locator(".landing-cta").get_attribute("href") == "/app")
            record("Skip link is available", page.locator("#skip-to-main").count() == 1)
            axe_scan("Public landing page")

            page.locator(".landing-cta").click()
            page.locator(".app-shell").wait_for(state="visible")
            record("App opens directly without a sign-in screen", page.locator(".app-shell").count() == 1)
            record("App has no sign-in or sign-out controls", page.get_by_text("Sign in", exact=True).count() == 0 and page.get_by_text("Sign out", exact=True).count() == 0)
            record("App has no footer", page.locator("footer").count() == 0)
            record("Navigation has no contract library or reference material tabs", page.get_by_role("navigation").get_by_text("Contracts Library", exact=True).count() == 0 and page.get_by_role("navigation").get_by_text("Reference Materials", exact=True).count() == 0)
            record("Navigation includes Settings", page.get_by_role("navigation").get_by_text("Settings", exact=True).count() == 1)
            record("App does not expose infrastructure diagnostics", page.get_by_text("Python API", exact=False).count() == 0 and page.get_by_text("Firebase", exact=False).count() == 0)
            record("App has one primary page heading", page.locator("main h1").count() == 1)
            record("Main landmark has a programmatic focus target", page.locator("main#main-content[tabindex='-1']").count() == 1)
            record("Rendered buttons have explicit types", page.locator("button:not([type])").count() == 0)
            fields_named = page.locator("input:not([type='hidden']), select, textarea").evaluate_all(
                "fields => fields.every(field => Boolean(field.getAttribute('aria-label') || field.getAttribute('aria-labelledby') || field.labels?.length))"
            )
            record("Visible form fields have accessible names", fields_named)
            record("Reviews page has a New Review action", page.locator(".app-page-title [data-action='start-review']").count() == 1)
            record("Reviews page uses a flat list rather than statistic cards", page.locator(".stat-grid, .stat-tile").count() == 0)
            axe_scan("Application home on desktop")

            page.locator("[data-action='navigate'][data-section='settings']").click()
            page.locator("[data-action='set-theme']").wait_for(state="visible")
            record("Settings navigation moves focus to destination heading", page.evaluate("document.activeElement?.matches('#main-content h1')"))
            page.locator("[data-action='set-theme'][data-value='dark']").click()
            record("Dark theme updates document state", page.locator("html").get_attribute("data-theme") == "dark")
            record("Theme control retains keyboard focus", page.evaluate("document.activeElement?.getAttribute('data-value') === 'dark'"))
            selected_background = page.locator("[data-action='set-theme'][data-value='dark']").evaluate("element => getComputedStyle(element).backgroundColor")
            record("Dark selected setting uses a neutral, non-blue surface", page.evaluate("value => { const m = value.match(/[0-9.]+/g).map(Number); return m.length >= 3 && m[2] <= m[0] + 3; }", selected_background), selected_background)
            page.locator(".app-primary-nav [data-section='new']").click()
            upload_background = page.locator(".upload-zone").evaluate("element => getComputedStyle(element).backgroundColor")
            record("Dark upload zone uses a neutral charcoal surface", page.evaluate("value => { const m = value.match(/[0-9.]+/g).map(Number); return m.length >= 3 && m[2] <= m[0] + 3; }", upload_background), upload_background)
            page.locator(".app-primary-nav [data-section='settings']").click()
            page.locator("[data-action='set-font'][data-value='large']").click()
            record("Large typography sets 1.5em root scale", page.locator("html").evaluate("element => getComputedStyle(element).fontSize") == "24px")
            record("Font control retains keyboard focus", page.evaluate("document.activeElement?.getAttribute('data-value') === 'large'"))
            page.locator("[data-action='set-language'][data-value='fr']").click()
            record("French selection updates document language", page.locator("html").get_attribute("lang") == "fr-CA")
            record("French settings heading is translated", (page.locator("main h1").text_content() or "").strip() == "Paramètres")
            record("Language control retains keyboard focus", page.evaluate("document.activeElement?.matches('[data-action=set-language]')"))
            record("Segmented controls expose pressed state", page.locator(".segmented-control button").evaluate_all("items => items.length > 0 && items.every(item => item.hasAttribute('aria-pressed'))"))
            axe_scan("French settings, dark theme and large typography")

            page.locator("[data-action='set-font'][data-value='small']").click()
            record("Small typography sets 0.85em root scale", page.locator("html").evaluate("element => getComputedStyle(element).fontSize") == "13.6px")
            page.locator("[data-action='set-font'][data-value='medium']").click()
            record("Medium typography sets 1.25em root scale", page.locator("html").evaluate("element => getComputedStyle(element).fontSize") == "20px")
            page.locator("[data-action='set-theme'][data-value='light']").click()
            record("Light theme restores document state", page.locator("html").get_attribute("data-theme") == "light")
            axe_scan("French settings, light theme and medium typography")

            page.locator("[data-action='set-language'][data-value='en']").click()
            for section in ["new", "recent", "legalQa", "settings"]:
                page.locator(f".app-primary-nav [data-action='navigate'][data-section='{section}']").click()
                page.locator("main h1").wait_for(state="visible")
                fields_named = page.locator("input:not([type='hidden']), select, textarea").evaluate_all(
                    "fields => fields.every(field => Boolean(field.getAttribute('aria-label') || field.getAttribute('aria-labelledby') || field.labels?.length))"
                )
                record(f"{section} page: all form fields have accessible names", fields_named)
                record(f"{section} page: no missing button types", page.locator("button:not([type])").count() == 0)
                if section == "new":
                    record("New Review has no reference-material or privacy side panels", page.get_by_text("Reference Materials", exact=True).count() == 0 and page.get_by_text("Privacy protection", exact=True).count() == 0 and page.locator(".review-aside").count() == 0)
                    record("New Review has no Save as draft action", page.get_by_text("Save as draft", exact=True).count() == 0)
                axe_scan(f"{section} page")

            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.locator(".landing-card").first.wait_for(state="visible")
            mobile_columns = page.locator(".landing-cards").evaluate("element => getComputedStyle(element).gridTemplateColumns.split(' ').length")
            record("Landing cards stack on narrow mobile screens", mobile_columns == 1, str(mobile_columns))
            record("Mobile landing page has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
            page.locator(".landing-cta").click()
            page.locator(".app-shell").wait_for(state="visible")
            page.set_viewport_size({"width": 320, "height": 780})
            page.wait_for_timeout(100)
            dimensions = page.evaluate("`${document.documentElement.scrollWidth}px document / ${window.innerWidth}px viewport`")
            record("320px application viewport has no horizontal overflow", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), dimensions)
            record("320px layout preserves visible main heading", page.locator("main h1").is_visible())
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
