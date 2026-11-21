# Mataba implementation decisions — 2.9.10

## Application structure

- One application server: Python + FastAPI in `app/main.py`.
- HTML templates: `app/templates/`.
- CSS, public Firebase web configuration and native JavaScript modules: `app/static/`.
- FastAPI serves the templates, static assets and API endpoints on the same origin.
- No `frontend/` folder, TypeScript files, Node.js runtime, npm package manifest, build command or generated `public/` directory.
- Python dependencies are declared in root `requirements.txt`; development/testing dependencies are in `requirements-dev.txt`.

## Browser dependencies

The browser loads fixed, version-pinned browser libraries from CDN URLs declared in `app/templates/index.html`: Firebase Web SDK, PDF.js, Mammoth, Dexie and fflate. These run in the browser. They are not a separate application server and do not require Node.js/npm during local development or deployment.

## Deployment

- Root `vercel.json` configures `app/main.py` in Montréal (`yul1`).
- The FastAPI function bundle includes `app/templates/**`, `app/static/**` and `firebase/ai_logic_templates/**`.
- No frontend build or pre-deployment compilation step is required.
- API responses are `no-store`; baseline security headers are configured.
- Firebase Hosting is not used. `firebase.json` is for rules and Emulator Suite configuration only.

## AI and data handling

- Firebase AI Logic is the only cloud Gemini integration.
- FastAPI calls the Firebase AI Logic server prompt-template interface with Google OAuth credentials; no direct Google Gen AI or Vertex AI model SDK is used.
- Browser Firebase SDK use covers silent anonymous Firebase Auth sessions (no user-facing sign-in), App Check, Firestore client access under tenant rules and supported on-device Gemini Nano functionality. Anonymous sign-in must be enabled in the Firebase project.
- Service-account credentials are provided through the server environment and never placed in `app/static/config.js`.

## Phase requirements preserved

- Phase 1: Firebase AI Logic prompt templates, structured responses, Canadian region/consumption checks and fail-closed behavior.
- Phase 2: browser PDF/DOCX/TXT extraction, local PII detection/redaction, encrypted IndexedDB PII vault and evidence metadata.
- Phase 3: contract analysis, source citation verification, lawyer-style report and gated HR sections.
- Phase 4: excluded as requested.
- Phase 5: Firebase ID token/App Check checks, request-size and rate limits, residual-PII guard and tenant rules.
- Phase 6: EN/FR UI, keyboard/focus behavior, responsive navigation, themes, font scaling and accessibility behavior.

## Entry and guest-session behavior

- `/` serves the public landing page; its main action opens `/app` directly.
- `/signin` redirects to `/app` for legacy bookmarks. No email/password sign-in or account controls are presented.
- With Firebase configured, the browser silently provisions an anonymous guest session for verified API requests and tenant-scoped cloud persistence.
- Without Firebase configured, the app uses a stable local guest identity for IndexedDB records. Cloud API features remain unavailable until Firebase and App Check are configured.

## Legal Q&A scope

- `/qa` is independent of contract upload and requires a Firebase anonymous guest session and App Check.
- Employment law is the only current law type.
- Jurisdictions include federal, provincial/territorial and municipal. Municipal questions capture the municipality and parent jurisdiction.
- `MUNICIPAL_LAW_SOURCES` is an allowlisted registry keyed by parent jurisdiction, municipality and law type. Only registered official source URLs can be fetched.
- There are no municipal employment-law entries in this release. The parent statute is used and identified as the source level actually checked; it is not represented as a municipal bylaw.
- Citation excerpts must match retrieved official legislation. Insufficient evidence does not produce a guessed answer.

## Document extraction

- PDF.js extracts selectable PDF text page by page; scanned PDFs are not OCR-processed.
- Mammoth extracts DOCX text. Explicit page-break markers can define page boundaries; otherwise the app does not invent pagination.
- TXT files are read locally in the browser.
- Pasted contract text follows the same sanitization and analysis pipeline as uploaded documents.

## Production verification

Local tests do not prove the Vercel project or client's Firebase configuration. Verify the Preview deployment, function region, Firebase Admin authentication, App Check, Firebase AI Logic template permissions, supported model/location and browser CDN availability before production.
