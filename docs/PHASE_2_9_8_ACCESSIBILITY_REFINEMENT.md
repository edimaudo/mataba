# Mataba 2.9.8 accessibility and theme refinement

## Changes

- Added a final dark-mode component override to remove blue-tinted backgrounds from selected tabs, hover states, upload zones, badges, icon surfaces and information panels. Form controls, browser autofill and native checkbox/radio accents also use neutral dark surfaces.
- Introduced a warm neutral focus indicator and restrained accent treatment.
- Applied Inter consistently to the document, body, buttons and form controls. The Inter web font is loaded from Google Fonts, with system sans-serif fallbacks.
- Kept the requested type scale: Small 0.85em, Medium 1.25em, Large 1.5em.
- Added automated contrast checks for core text and focus/accent tokens.

## Validation

- Python test suite: 116 passed.
- Python compilation: passed.
- Static application validation: passed.
- JavaScript syntax validation: passed.
- Browser-rendered visual and axe checks were attempted but could not complete because local browser navigation was blocked by the execution environment (`ERR_BLOCKED_BY_ADMINISTRATOR`).

## Conformance limitation

These changes improve selected WCAG 2.2 AA criteria, particularly text contrast for tested tokens, visible keyboard focus and consistent text scaling. They do not establish full WCAG conformance. A complete audit still requires rendered-page testing of every state and component, keyboard-only operation, screen-reader testing, zoom/reflow checks, error identification, and review of any content rendered from dynamic data. The Inter web font also requires access to Google Fonts; system sans-serif fallbacks remain available if it cannot load.

- Added a versioned stylesheet URL (`styles.css?v=2.9.8`) on the app and landing templates to prevent browsers from reusing the previous theme stylesheet.
