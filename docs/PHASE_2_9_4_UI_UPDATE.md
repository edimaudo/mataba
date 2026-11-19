# Mataba 2.9.4 UI update

## Changes

- `/` now serves a public landing page independently of Firebase Authentication.
- `/signin` serves the sign-in/create-account screen.
- `/app` serves the authenticated application shell; `/qa` remains available for standalone Legal Q&A.
- The public and authenticated interfaces use the supplied KaziLaw reference direction: Inter, compact horizontal navigation, restrained blue and muted gold accents, simple borders and a centered content width.
- Removed eyebrow labels throughout the application interface.
- Removed the local-preview identity, local-preview entry action and the banner that implied cloud AI/account sync were available in a local-only session.
- When Firebase Authentication is not configured, the sign-in screen displays a concise configuration requirement; the public landing page remains available.
- Existing backend routes, contract workflows, privacy controls, legal Q&A and Firebase AI Logic integration remain in place.

## Validation

- Python test suite: 100 passed.
- Python bytecode compilation: passed.
- Native JavaScript syntax checks: passed.
- Static asset validation: passed.
- Browser rendering and live Firebase sign-in were not tested in this environment.
