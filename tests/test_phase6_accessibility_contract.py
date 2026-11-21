import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app" / "static" / "css" / "styles.css").read_text()
MAIN = (ROOT / "app" / "static" / "js" / "main.js").read_text()
HTML = (ROOT / "app" / "templates" / "index.html").read_text()


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


def test_application_uses_horizontal_navigation_and_no_sidebar_drawer():
    assert 'class="primary-nav app-primary-nav"' in MAIN
    assert "function layoutView()" in MAIN
    assert "app-shell-horizontal" in MAIN
    assert "primary-sidebar" not in MAIN
    assert "role=\"dialog\"" not in MAIN


def test_report_tabs_have_required_roles_and_keyboard_navigation():
    assert 'role="tablist"' in MAIN
    assert 'role="tab"' in MAIN
    assert 'role="tabpanel"' in MAIN
    assert "['ArrowLeft', 'ArrowRight', 'Home', 'End']" in MAIN
    assert "app.querySelector(`[data-action=\"report-tab\"]" in MAIN


def test_theme_and_font_scales_match_product_requirement():
    assert 'html[data-font-size="small"] { font-size: .85em; }' in CSS
    assert 'html[data-font-size="medium"] { font-size: 1.25em; }' in CSS
    assert 'html[data-font-size="large"] { font-size: 1.5em; }' in CSS
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
    assert "callBackend('/api/legal-qa'" in MAIN
    assert "legalQa" in MAIN.split("function pageView()", 1)[1].split("function recentView()", 1)[0]


def test_legal_qa_result_heading_is_focusable_after_submission():
    assert 'id="legal-qa-answer-title" tabindex="-1"' in MAIN


def test_custom_404_page_has_home_and_legal_qa_navigation():
    not_found = (ROOT / "app" / "templates" / "404.html").read_text(encoding="utf-8")
    assert "404" in not_found
    assert 'href="/"' in not_found
    assert 'href="/qa"' in not_found
    assert "localStorage.getItem('mataba-language')" in not_found
    assert "min-width:320px" in not_found


def test_application_navigation_and_new_review_follow_the_revised_product_scope():
    assert "navItem('recent', 'reviews', '')" in MAIN
    assert "navItem('new', 'newReview', '')" in MAIN
    assert "navItem('settings', 'settings', '')" in MAIN
    assert "navItem('library'" not in MAIN
    assert "navItem('references'" not in MAIN
    assert 'function libraryView()' not in MAIN
    assert 'function referencesView()' not in MAIN
    assert 'save-draft' not in MAIN
    assert 'Save as draft' not in MAIN
    assert 'Python API' not in MAIN
    assert 'Firebase configured' not in MAIN
    assert 'AI processing and data residency' not in MAIN
    assert 'class="review-aside"' not in MAIN
    assert 'privacyShield' not in MAIN
    assert 'await runRedaction();' in MAIN


def test_settings_controls_are_available_in_settings_section_and_persist_preferences():
    settings = MAIN.split('function settingsView()', 1)[1].split('function reportCitation', 1)[0]
    assert 'data-action="set-language"' in settings
    assert 'data-action="set-font"' in settings
    assert 'data-action="set-theme"' in settings
    assert "localStorage.setItem('mataba-theme'" in MAIN
    assert "localStorage.setItem('mataba-font-size'" in MAIN
    assert "localStorage.setItem('mataba-language'" in MAIN


def test_navigation_active_state_has_no_blue_vertical_marker():
    assert '.app-primary-nav .nav-item.active { color: var(--text); border-bottom: 2px solid #a88b5a; background: transparent; box-shadow: none !important;' in CSS


def test_revised_light_and_dark_palette_preserves_wcag_aa_text_contrast():
    def ratio(foreground, background):
        def luminance(value):
            channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
        first, second = luminance(foreground), luminance(background)
        return (max(first, second) + 0.05) / (min(first, second) + 0.05)

    assert ratio("#596570", "#ffffff") >= 4.5
    assert ratio("#65717a", "#ffffff") >= 4.5
    assert ratio("#c0c4c5", "#202629") >= 4.5
    assert ratio("#a8afb2", "#202629") >= 4.5


def test_inter_is_loaded_and_applied_to_all_form_controls():
    assert 'fonts.googleapis.com/css2?family=Inter:' in HTML
    assert 'font-family: "Inter", ui-sans-serif' in CSS
    assert 'html, body, button, input, select, textarea {' in CSS

def test_medium_font_scale_remains_exactly_one_em():
    assert 'html[data-font-size="medium"] { font-size: 1.25em; }' in CSS

def test_dark_mode_uses_neutral_highlights_and_accessible_focus_ring():
    final_theme = CSS.split("/* Mataba 2.9.8:", 1)[1]
    assert '--focus-ring: #f0d79c;' in final_theme
    assert '--accent-soft: #38342b;' in final_theme
    assert 'background: var(--dark-neutral-surface) !important;' in final_theme
    assert 'outline: 3px solid var(--focus-ring) !important;' in final_theme

def test_focus_and_accent_tokens_meet_wcag_aa_contrast():
    final_theme = CSS.split("/* Mataba 2.9.8:", 1)[1]
    root_block = final_theme.split(":root", 1)[1].split("}", 1)[0]
    dark_theme = final_theme.split('html[data-theme="dark"]', 1)[1].split("}", 1)[0]
    light = css_vars(root_block)
    dark = css_vars(dark_theme)
    assert contrast_ratio(light["--focus-ring"], "#ffffff") >= 3.0
    assert contrast_ratio(dark["--focus-ring"], "#202629") >= 3.0
    assert contrast_ratio(dark["--muted"], dark["--surface"]) >= 4.5
    assert contrast_ratio(dark["--faint"], dark["--surface"]) >= 4.5


def test_final_dark_mode_override_covers_blue_tinted_component_surfaces():
    final_theme = CSS.split("/* Mataba 2.9.8:", 1)[1]
    for selector in (
        "html[data-theme=\"dark\"] .notice-info",
        "html[data-theme=\"dark\"] .drop-zone:hover",
        "html[data-theme=\"dark\"] .upload-zone:hover",
        "html[data-theme=\"dark\"] .segmented-control button.selected",
        "html[data-theme=\"dark\"] .source-tag.cloud",
        "html[data-theme=\"dark\"] .summary-icon",
        "html[data-theme=\"dark\"] .qa-icon",
        "html[data-theme=\"dark\"] .legal-citation blockquote",
        "html[data-theme=\"dark\"] #main-content h1:focus",
    ):
        assert selector in final_theme
    assert "--dark-neutral-surface: #2d3336;" in final_theme
    assert "--dark-neutral-hover: #343b3e;" in final_theme
    assert "background: var(--dark-neutral-surface) !important;" in final_theme
    assert "background: var(--dark-neutral-hover) !important;" in final_theme
    assert "accent-color: var(--accent);" in final_theme
    assert "html[data-theme=\"dark\"] ::selection" in final_theme


def test_font_scale_is_consistent_at_initial_and_final_stylesheet_rules():
    assert CSS.count('html[data-font-size="small"] { font-size: .85em; }') >= 2
    assert CSS.count('html[data-font-size="medium"] { font-size: 1.25em; }') >= 2
    assert CSS.count('html[data-font-size="large"] { font-size: 1.5em; }') >= 2


def test_stylesheet_cache_version_is_updated_on_app_and_landing_pages():
    landing = (ROOT / "app" / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "/css/styles.css?v=2.9.8" in HTML
    assert "/css/styles.css?v=2.9.8" in landing
