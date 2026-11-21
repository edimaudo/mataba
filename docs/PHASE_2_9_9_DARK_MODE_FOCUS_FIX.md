# Mataba 2.9.9 dark-mode and focus correction

## Root cause

The 2.9.8 stylesheet set a gold focus ring globally with `:focus-visible`, added gold outlines to focused form fields, and used gold for dark-mode focus and selected-state tokens. Settings click handlers also restored focus after re-rendering regardless of whether the activation came from a pointer or keyboard. These rules made ordinary pointer interactions appear as yellow boxes.

## Changes

- Removed the duplicated 2.9.7 and 2.9.8 accessibility override blocks and consolidated the design tokens in one versioned 2.9.9 block.
- Changed focus indication to a neutral slate outline, shown only for `:focus-visible` keyboard-style focus.
- Removed outlines and shadows for pointer focus (`:focus:not(:focus-visible)`).
- Limited settings and report-tab focus restoration to keyboard activation (`event.detail === 0`).
- Replaced dark-mode amber/gold selected, button, badge, warning, upload, hover and selection fills with neutral graphite colours.
- Updated the app version and stylesheet cache key to 2.9.9.
- Preserved Inter and the Small 0.85em / Medium 1.25em / Large 1.5em scale.

## Validation

The Python suite, Python compilation, JavaScript syntax check, static-asset validation and CSS parser check are run for this release. A full browser-based visual audit and WCAG 2.2 AA certification are separate requirements and are not inferred from source-level checks.
