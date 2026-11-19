# Mataba implementation decisions — 2.9.2

## Application layout

- There is no `backend/` directory. The Python application is organized as the standard `app/` package.
- `app/main.py` is the FastAPI application entrypoint and is a supported zero-configuration Vercel FastAPI layout.
- Python application dependencies are declared in the root `requirements.txt`; development/test dependencies are in `requirements-dev.txt`.
- Frontend source stays in `frontend/`. The Python build script generates `public/`, which Vercel serves through its CDN.
- `firebase/` contains Firestore/Storage rules and Firebase AI Logic prompt-template source. `firebase.json` is only for rules and Emulator Suite configuration; it does not enable Firebase Hosting.

## Vercel configuration

- Root `vercel.json` is included.
- FastAPI entrypoint: `app/main.py`.
- FastAPI Function region: Montréal (`yul1`).
- Vercel build command: install the frontend browser packages, then run `python scripts/build.py`.
- Prompt templates and generated `public/` assets are included in the FastAPI Function bundle where the application may need them.
- Tests, build scripts, TypeScript source and installed frontend packages are excluded from the deployed function bundle.
- API responses are marked `no-store`; baseline security headers are configured.
- Vercel's static CDN serves only public application assets. Contract text and user records are sent only to authenticated API/Firebase services, not placed in the static asset directory.

## Application architecture

- One application server: Python + FastAPI.
- Frontend source: HTML5, vanilla CSS3 and TypeScript.
- Firebase AI Logic is the exclusive cloud Gemini integration.
- FastAPI calls Firebase AI Logic's server prompt-template REST interface with Google OAuth credentials; no direct Google Gen AI or Vertex AI model SDK is used.
- Browser Firebase SDK use remains limited to browser-required Firebase Auth/App Check, on-device Gemini Nano and Firestore client access under tenant rules.
- Firebase Hosting is not required.

## Build tooling

- All custom build, development, validation, deployment configuration and test orchestration is Python.
- `scripts/build.py` invokes the standalone native esbuild compiler to compile TypeScript; browsers do not execute TypeScript source.
- `scripts/dev.py` starts one Python FastAPI/Uvicorn server and watches frontend files using Python `watchfiles`.
- `frontend/package.json` declares browser libraries and the esbuild compiler; it contains no application-server or development-server scripts. npm is used only to obtain these JavaScript ecosystem packages and the compiler at build time.
- PDF.js ships a vendor module worker as `.mjs`; the build copies it to the served worker asset. There are no authored `.mjs` application scripts.

## Phase requirements preserved

- Phase 1: Firebase AI Logic server prompt templates, structured responses, Canadian region/consumption checks and fail-closed behavior.
- Phase 2: browser document extraction, local PII detection/manual review, encrypted IndexedDB PII vault and evidence metadata.
- Phase 3: contract analysis, source citation verification, lawyer-style report and gated HR sections.
- Phase 4: excluded as requested.
- Phase 5: Firebase ID token/App Check checks, request-size and rate limits, residual-PII guard, tenant rules and account deletion sequence.
- Phase 6: EN/FR UI, keyboard/focus behavior, responsive navigation, themes, font scaling and accessibility checks.

## Credential handling

- Local development may use Google Application Default Credentials.
- Vercel functions use `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` as a sensitive environment variable to initialize Firebase Admin and obtain OAuth tokens for the Firebase AI Logic server-template REST call.
- The service-account secret must never be placed in `frontend/public/config.js`, committed to source control, or exposed to the browser.

## Remaining deployment verification

A local test suite does not prove that a Vercel deployment or the client's Firebase project is configured correctly. Verify the Vercel Preview, the `yul1` function region, static asset routes, Firebase Admin authentication, App Check, Firebase AI Logic template access and the Montreal model/consumption configuration before production.

## Standalone legal Q&A and custom 404 (2.9.1)

- `/qa` is a separate authenticated app page and does not require a contract, contract ID or uploaded file.
- Initial scope is Canadian employment standards/labour legislation, with one official principal statute for federal and each provincial/territorial jurisdiction. It does not claim to cover municipal bylaws, every regulation or every area of law.
- FastAPI retrieves official legislation from a fixed domain-allowlisted registry, ranks relevant passages, sends those passages through the existing Firebase AI Logic server-template integration, and verifies every returned citation against the retrieved text.
- No-evidence responses withhold unsupported conclusions. User questions containing obvious residual personal identifiers are rejected before source retrieval or AI inference.
- `frontend/404.html` is built into `public/404.html`; FastAPI returns a true HTTP 404 for unknown browser paths and a non-HTML 404 for missing static assets.
- The legal Q&A page requires Firebase sign-in/App Check as other online AI features. “No contract required” does not mean anonymous access.


## Mataba 2.9.1 — Legal category and dual-mode contract input

- Independent Legal Q&A now has an explicit law-type selector. Employment law is the only allowed value at both the frontend and API schema; future categories require their own official-source registry and tests.
- Contract review now offers two modes modeled on KaziLaw's Full Document / Specific Clause interaction: upload PDF/DOCX/TXT, or paste contract text. Pasted text is wrapped as an in-memory TXT File and passes through the existing browser extraction, PII detection/redaction, manual review, and the same analysis endpoint.
- PDF extraction remains page-by-page for selectable text. DOCX extraction uses Mammoth; page references are preserved only when explicit page breaks exist, otherwise citations refer to an unpaginated text section. OCR is not enabled for scanned PDFs.


## Mataba 2.9.2 — Municipal jurisdiction support

- Legal Q&A keeps Employment law as its only selectable law type.
- Jurisdiction selection now supports Federal, Province/Territory and Municipal. Municipal scope requires a municipality name and its parent province or territory.
- The request schema validates the hierarchy and carries the local context through FastAPI into the Q&A prompt and response metadata.
- `LawSource` records its actual jurisdiction level. A curated `MUNICIPAL_LAW_SOURCES` registry resolves sources by parent code, normalized municipality and law type. Only an exact registered source with a matching parent jurisdiction can be selected; user-provided URLs are never accepted.
- The municipal employment-law registry is empty in this release. Therefore municipal employment questions fall back to the parent employment statute. The prompt explicitly prevents the model from describing that source as a municipal bylaw, and the UI identifies the level actually checked.
- Adding municipal coverage means registering and testing the relevant authoritative municipal source for the applicable law type. A typed municipality alone is not treated as evidence that a municipal rule exists.
