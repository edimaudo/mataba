# Mataba 2.9.5 UI update

## Changes

- Removed the landing-page footer.
- Removed the landing header links for “How it works” and “Legal coverage”; the header now contains only the Mataba wordmark.
- Removed the sign-in link and sign-in call to action. “Start a review” opens `/app` directly.
- Rebuilt “Review the terms that matter.” and “Canadian legal coverage” as a two-column card row. Both cards stretch to the same row height and stack on narrow screens.
- Removed the email/password sign-in and account controls from the application interface.
- The app now establishes a Firebase anonymous session silently when the Firebase web configuration and Anonymous provider are enabled. This keeps ID-token verification on cloud API requests without showing a sign-in page.
- When Firebase is not configured, the app opens with a persistent device-local guest identity so local drafts remain usable. Cloud analysis and Legal Q&A remain blocked until the Firebase guest session and App Check are configured.
- `/signin` now redirects to `/app` for existing bookmarks; it no longer serves a sign-in page.
- Kept the existing FastAPI, native JavaScript, contract review, privacy, legal-reference and Legal Q&A architecture.

## Validation

- Python test suite: 100 passed.
- Python bytecode compilation: passed.
- JavaScript syntax checks: passed.
- Static asset validation: to be rerun for this build.
- Browser rendering and live Firebase anonymous authentication require the target Firebase project and were not verified in this environment.
