import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "src" / "styles.css").read_text()
MAIN = (ROOT / "frontend" / "src" / "main.ts").read_text()
HTML = (ROOT / "frontend" / "index.html").read_text()


def css_vars(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:\s*(#[0-9a-fA-F]{6})", block))


def relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]

    def linearize(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearize(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_skip_link_points_to_main_landmark():
    assert 'href="#main-content"' in HTML
    assert 'id="skip-to-main"' in HTML
    assert 'id="main-content" tabindex="-1"' in MAIN


def test_navigation_drawer_is_modal_and_keyboard_managed_on_mobile():
    assert 'role="${state.mobileNavOpen ? \'dialog\' : \'complementary\'}"' in MAIN
    assert 'aria-modal="true"' in MAIN
    assert "sidebar.inert = closed" in MAIN
    assert "main.inert = modalNavigation" in MAIN
    assert "if (event.key === 'Tab' && sidebar)" in MAIN
    assert "if (event.key === 'Escape')" in MAIN
    assert "window.matchMedia('(max-width: 850px)')" in MAIN


def test_report_tabs_have_required_roles_and_keyboard_navigation():
    assert 'role="tablist"' in MAIN
    assert 'role="tab"' in MAIN
    assert 'role="tabpanel"' in MAIN
    assert "['ArrowLeft', 'ArrowRight', 'Home', 'End']" in MAIN
    assert "app!.querySelector<HTMLElement>(`[data-action=\"report-tab\"]" in MAIN


def test_theme_and_font_scales_match_product_requirement():
    assert 'html[data-font-size="small"] { font-size: .75em; }' in CSS
    assert 'html[data-font-size="medium"] { font-size: 1em; }' in CSS
    assert 'html[data-font-size="large"] { font-size: 1.25em; }' in CSS
    assert 'html[data-theme="dark"]' in CSS


def test_normal_text_palette_meets_wcag_aa_contrast_in_light_and_dark_themes():
    root_block = CSS.split(":root", 1)[1].split("}", 1)[0]
    dark_block = CSS.split('html[data-theme="dark"]', 1)[1].split("}", 1)[0]
    light = css_vars(root_block)
    dark = css_vars(dark_block)
    assert contrast_ratio(light["--muted"], light["--surface"]) >= 4.5
    assert contrast_ratio(light["--faint"], light["--surface"]) >= 4.5
    assert contrast_ratio(dark["--muted"], dark["--surface"]) >= 4.5
    assert contrast_ratio(dark["--faint"], dark["--surface"]) >= 4.5


def test_visible_focus_and_reduced_motion_preferences_are_supported():
    assert ':focus-visible { outline: 3px solid' in CSS
    assert '#main-content:focus { outline: 3px solid' in CSS
    assert '@media (prefers-reduced-motion: reduce)' in CSS


def test_root_layout_supports_320_pixel_viewport():
    assert 'body { margin: 0; min-width: 320px;' in CSS
    assert '@media (max-width: 620px)' in CSS


def test_dark_theme_accent_text_uses_light_contrast_tokens():
    dark_block = CSS.split('html[data-theme="dark"]', 1)[1].split("}", 1)[0]
    dark = css_vars(dark_block)
    assert contrast_ratio(dark["--blue"], dark["--surface"]) >= 4.5
    assert contrast_ratio(dark["--muted"], dark["--surface"]) >= 4.5
    assert contrast_ratio(dark["--faint"], dark["--surface"]) >= 4.5
    assert 'html[data-theme="dark"] .finding-category { color: #a6c7ff; }' in CSS
    assert 'html[data-theme="dark"] .verified-check { color: #8fe1bf; }' in CSS


def test_report_tabpanel_is_focusable_for_keyboard_users():
    assert 'role="tabpanel" tabindex="0" aria-labelledby=' in MAIN



def test_standalone_legal_qa_is_available_without_contract_upload():
    assert "legalQaView()" in MAIN
    assert 'data-form="legal-qa"' in MAIN
    assert 'No contract or uploaded document is required.' in MAIN
    assert "callBackend<LegalQAResponse>('/api/legal-qa'" in MAIN
    assert "legalQa" in MAIN.split("function pageView()", 1)[1].split("function recentView()", 1)[0]


def test_legal_qa_result_heading_is_focusable_after_submission():
    assert 'id="legal-qa-answer-title" tabindex="-1"' in MAIN


def test_custom_404_page_has_home_and_legal_qa_navigation():
    not_found = (ROOT / "frontend" / "404.html").read_text(encoding="utf-8")
    assert "404" in not_found
    assert 'href="/"' in not_found
    assert 'href="/qa"' in not_found
    assert "localStorage.getItem('mataba-language')" in not_found
    assert "min-width:320px" in not_found
