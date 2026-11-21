# Mataba 2.9.7 accessibility and theme refinement

## Changes

- Removed blue-tinted dark-mode section, selected-control, upload and informational surfaces in favour of neutral charcoal surfaces.
- Introduced a warm neutral focus indicator and restrained accent treatment.
- Applied Inter consistently to the document, body, buttons and form controls. The Inter web font is loaded from Google Fonts, with system sans-serif fallbacks.
- Kept the requested type scale: Small 0.75em, Medium 1em, Large 1.25em.
- Added automated contrast checks for core text and focus/accent tokens.

## Validation

- Python test suite: 113 passed.
- Python compilation: passed.
- Static application validation: passed.

## Conformance limitation

These changes improve selected WCAG 2.2 AA criteria, particularly text contrast for tested tokens, visible keyboard focus and consistent text scaling. They do not establish full WCAG conformance. A complete audit still requires rendered-page testing of every state and component, keyboard-only operation, screen-reader testing, zoom/reflow checks, error identification, and review of any content rendered from dynamic data. The Inter web font also requires access to Google Fonts; system sans-serif fallbacks remain available if it cannot load.
