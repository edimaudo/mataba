# Mataba 2.9.4

Mataba is a Canadian contract-review application. It is one **Python + FastAPI** application. The browser interface is plain **HTML, CSS and native JavaScript** served by that same FastAPI application. Firebase AI Logic is the cloud Gemini integration.

There is no separate frontend project, TypeScript, Node.js runtime, npm build, package manifest or generated frontend directory.

## Project structure

```text
mataba/
├── app/
│   ├── main.py                    # FastAPI routes and application entry point
│   ├── config.py
│   ├── credentials.py
│   ├── schemas.py
│   ├── security.py
│   ├── rate_limit.py
│   ├── services/                   # Python application logic
│   ├── templates/
│   │   ├── landing.html             # Public landing page at /
│   │   ├── index.html               # Sign-in and application shell
│   │   └── 404.html
│   └── static/
│       ├── config.js               # Public Firebase web-app settings only
│       ├── css/styles.css
│       └── js/                     # Native browser JavaScript modules
├── firebase/
│   ├── ai_logic_templates/
│   ├── firestore.rules
│   └── storage.rules
├── tests/                          # Python tests
├── scripts/                        # Python run and validation scripts
├── requirements.txt
├── requirements-dev.txt
├── firebase.json                   # Rules and emulator configuration only
└── vercel.json
```

FastAPI serves the public landing page at `/`, sign-in at `/signin`, the authenticated application at `/app` (and standalone Legal Q&A at `/qa`), static files and all `/api/*` endpoints. The browser JavaScript is already in executable `.js` files; no frontend compilation or generated `public/` directory is required.

The browser loads the pinned Firebase, PDF.js, Mammoth, Dexie and fflate libraries directly from their CDN URLs in the HTML import map/script tags. These are browser libraries, not a Node application or a separate frontend server. The only Python runtime dependency installation is from `requirements.txt`.

## Contract input

Contract review supports:

- **Upload document:** PDF, DOCX or TXT. PDF.js extracts selectable PDF text page by page. Mammoth extracts DOCX text in the browser. Explicit DOCX page breaks are retained when present; otherwise the app does not invent page numbers. Scanned/image-only PDFs are not OCR-processed in this release.
- **Paste text:** Pasted content enters the same extraction, local PII redaction, manual confirmation, evidence-indexing and contract-analysis flow as an uploaded file. Only the user-reviewed sanitized text is sent for cloud analysis.

## Independent Legal Q&A

Legal Q&A is available at `/qa` and does not require an uploaded contract. **Employment law** is the only law type in this release. Jurisdiction can be federal, provincial/territorial or municipal. Municipal selection requires its parent province/territory and a municipality name.

The backend has a curated municipal source registry keyed by parent jurisdiction, municipality and law type. Only explicitly registered official sources are eligible. No municipal employment-law sources are registered in this release, so a municipal employment question uses the parent employment statute and identifies the level of the source actually checked. It does not describe a provincial or territorial statute as a municipal bylaw.

## Request flow

```text
Browser: HTML + CSS + native JavaScript
                 |
                 | same-origin /api requests
                 v
           Python FastAPI
                 |
                 v
           Firebase AI Logic
                 |
                 v
            Gemini model
```

FastAPI handles authentication and App Check verification, request validation, application logic, Firebase AI Logic prompt-template calls, citation verification, rate limits and privacy checks. The browser Firebase SDK is used for Firebase sign-in, App Check tokens, Firestore persistence and supported on-device Gemini Nano functionality.

## Local setup

Create a Python environment and install the Python dependencies:

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

Set up Firebase configuration:

```bash
cp .env.example .env
```

Fill in the required values. For local Google credentials, use Application Default Credentials:

```bash
gcloud auth application-default login
```

The public Firebase Web App settings belong in `app/static/config.js`. Never put service-account credentials or private keys there. For Vercel, set the base64-encoded service-account JSON in the sensitive `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` environment variable.

Run the application:

```bash
python scripts/dev.py
```

Open `http://127.0.0.1:8080` for the public landing page. Sign in at `/signin`; the application is served at `/app`. The development script starts one Uvicorn/FastAPI server. No browser build or separate frontend process is run.

Alternatively, run FastAPI directly:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Vercel deployment

The root `vercel.json` configures the FastAPI function in Montréal (`yul1`), includes the application templates, static files and Firebase AI Logic prompt templates, and applies the response headers. There is no build command.

1. Import the repository into Vercel and keep the repository root as the project root.
2. Configure the environment variables from `.env.example` in Vercel Project Settings.
3. Add `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` as a sensitive environment variable.
4. Confirm the Function Region is Montréal (`yul1`).
5. Deploy a Preview and test `/`, `/qa`, an unknown route, `/api/health`, Firebase Authentication, App Check, official-law retrieval and a staging Firebase AI Logic request.
6. Promote to Production only after the client's privacy and regional-processing checks pass.

The Vercel CLI is only needed when deploying from a terminal; it is not part of the application runtime:

```bash
vercel link
vercel deploy
vercel deploy --prod
```

See [docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md) for the deployment checklist.

## Firebase rules

`firebase.json` configures Firestore/Storage rules and local emulators. It does not configure Firebase Hosting or deploy a second web application.

```bash
firebase emulators:start --project demo-mataba-rules --only auth,firestore,storage
```

In another terminal:

```bash
python scripts/test_firebase_rules.py
```

## Validation

Run the Python tests and native asset check:

```bash
python -m pytest tests -q
python scripts/validate_static_assets.py
```

Optional browser acceptance tests use Python Playwright:

```bash
python -m playwright install chromium
python scripts/test_privacy_utils.py
python scripts/test_browser_ux.py
```

The browser tests load axe-core from its pinned CDN URL. They do not install or run Node.js.

## Implemented phases

- Phase 1: Firebase AI Logic prompt templates, structured responses, Canadian processing checks and fail-closed behavior.
- Phase 2: browser document extraction, local PII detection/redaction, encrypted IndexedDB PII vault and evidence metadata.
- Phase 3: contract analysis, source citation verification, lawyer-style report and gated HR report sections.
- Phase 4: excluded, as requested.
- Phase 5: Firebase ID token/App Check checks, request-size and rate limits, residual-PII guard, Firestore/Storage rules and account deletion sequence.
- Phase 6: English/French UI, keyboard/focus behavior, responsive navigation, light/dark theme, font scaling and accessibility support.
- Version 2.9.4: added the public KaziLaw-referenced landing page, separated `/signin` and `/app`, replaced the sidebar with compact horizontal navigation, removed eyebrow labels and removed the local-preview account path.

## Important limits before production

Vercel's `yul1` setting controls where the FastAPI function executes; it does not prove every downstream processor is in Canada. The Firebase AI Logic model and processing location must be independently confirmed in the client's project. Live Firebase AI Logic, App Check, model-region and end-to-end acceptance tests must be run against staging before production.

Legal Q&A currently covers employment standards and labour legislation only. The source registry includes a principal employment/labour statute for Canada and each province/territory. Municipal registry support exists, but there are no municipal employment-law entries yet. If retrieved text does not support an answer, Mataba withholds an unsupported conclusion. Firebase Authentication and App Check are required for online Q&A.

PDF page references are preserved. DOCX page references are only available where the file contains explicit page-break markers; scanned PDFs are not OCR-processed. The privacy scan is a best-effort safeguard and requires the user's manual review before cloud analysis.
