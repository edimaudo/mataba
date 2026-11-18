# Mataba 2.5.0 — Phase 1–3 implementation

Mataba is a Canadian-first contract review application with Canadian English (`en-CA`) and French (`fr-CA`) experiences.

This package contains the Phase 1–3 implementation. Phase 4 (additional folder/library management) was intentionally excluded from this delivery. Phase 5 (security acceptance testing) and Phase 6 (browser, accessibility and full UX validation) have not been started; they are the next workstream.

## Architecture

The frontend is browser-only. The backend is FastAPI + Firebase. Firebase AI Logic is the exclusive AI integration for cloud Gemini and the local Gemini Nano tasks.

```text
BROWSER / FRONTEND
Vanilla HTML + CSS + TypeScript
  - UI and navigation
  - PDF / DOCX / TXT extraction
  - On-device PII detection, manual review and tokenization
  - AES-GCM encrypted IndexedDB vault for reversible PII tokens
  - Firebase client SDK for authentication and user-scoped data services
  - Firebase AI Logic Gemini Nano with ONLY_ON_DEVICE for local tasks
                 |
                 | sanitized source text + Firebase ID token + App Check token
                 v
BACKEND: PYTHON FASTAPI + FIREBASE SERVICES
  FastAPI
    - verifies Firebase ID token and App Check token
    - validates payload, source IDs and report eligibility
    - orchestrates Firebase AI Logic server templates
    - verifies exact evidence citations and structures reports
                 |
                 | OAuth ADC token with cloud-platform scope
                 v
          FIREBASE AI LOGIC
          server prompt templates
                 |
                 v
          Gemini cloud model

Firebase managed backend services (where required by the PRD):
  - Firebase Authentication
  - Firebase App Check
  - Cloud Firestore
  - Cloud Storage for Firebase
```

There is **no React, Tailwind, Vite, JSX, Vertex AI Python SDK or Google Gen AI Python SDK** in this project. The browser does not call cloud Gemini directly. Online analysis and online follow-up go through FastAPI, which calls the Firebase AI Logic server-template REST API. The browser's Firebase AI Logic SDK instance is restricted to `InferenceMode.ONLY_ON_DEVICE` for Gemini Nano.

Firebase Hosting is not required. Host the static frontend on any suitable static host. Host FastAPI on a Python ASGI platform; Cloud Run is one option, not a Firebase Hosting requirement.

## Technology

| Area | Implementation |
|---|---|
| Frontend | Vanilla HTML5, CSS3 and TypeScript |
| Build | esbuild |
| Backend | Python 3.12+ and FastAPI |
| AI integration | Firebase AI Logic only |
| Cloud model | Gemini 3.8 Flash, subject to the regional capacity gate below |
| On-device model | Gemini Nano via Firebase AI Logic `ONLY_ON_DEVICE` |
| Authentication and App Check | Firebase Auth and App Check |
| Application data | Cloud Firestore and IndexedDB |
| Document extraction | PDF.js, Mammoth and explicit DOCX page-break parsing |
| Local privacy vault | Dexie / IndexedDB with AES-GCM encryption |

## Phase 1 — Firebase AI Logic integration

Implemented:

- FastAPI verifies the user's Firebase ID token and App Check token before any cloud AI request.
- The Python service calls Firebase AI Logic's official server prompt-template REST endpoint. It obtains its server-to-server OAuth token using Application Default Credentials with the `cloud-platform` scope.
- No direct Gemini or Vertex AI Python model client is used.
- Contract-analysis and follow-up Dotprompt source templates include typed input and structured JSON output schemas.
- Backend configuration, safe upstream error handling, and a service-health endpoint are included.
- Unsupported model/region/consumption-mode combinations fail closed; there is no silent global or US fallback.

### Montréal model and consumption-mode requirement

Google's current model documentation lists Gemini 3.8 Flash as supporting Montréal (`northamerica-northeast1`) in-region ML processing with **Provisioned Throughput**. Standard PayGo is listed for `global`, `us` and `eu`, not Montréal. Therefore the default configuration deliberately blocks cloud inference until the project has actually provisioned the required capacity.

In `backend/.env`, keep this false until the client project is configured and verified:

```dotenv
FIREBASE_AI_LOGIC_LOCATION=northamerica-northeast1
FIREBASE_AI_LOGIC_MODEL=gemini-3.8-flash
FIREBASE_AI_LOGIC_PROVISIONED_THROUGHPUT_ENABLED=false
```

After Provisioned Throughput has been purchased/configured for the model and region, the operator may set `FIREBASE_AI_LOGIC_PROVISIONED_THROUGHPUT_ENABLED=true`. This flag is an explicit operator assertion; the backend cannot independently prove the capacity reservation. The live staging inference and regional processing configuration must be validated before the setting is enabled in production.

Firebase AI Logic server prompt templates are currently a **Preview** feature and are not covered by an SLA. Treat the template create/lock/generate flow as a deployment prerequisite and staging gate.

## Phase 2 — privacy and document processing

Implemented:

- Local pattern screening and Gemini Nano detection where the browser/device supports it.
- Manual redactions are included in the same local masking pipeline.
- SIN checksum diagnostics are available, but all nine-digit SIN candidates are masked regardless of checksum to avoid privacy false negatives.
- Per-document namespaces make reversible tokens unique across contracts and reference materials.
- The reversible PII token map is saved only in the browser's IndexedDB vault, encrypted using AES-GCM with a non-extractable Web Crypto key. It is not sent to FastAPI, Firestore, Storage or Firebase AI Logic.
- The application loads the encrypted token map when an existing review is reopened. If local vault data is missing or cannot be decrypted, the sanitized report remains accessible and the UI shows a warning.
- PDF extraction preserves PDF page numbers.
- DOCX extraction recognizes explicit page breaks, rendered page-break markers and page-break-before markers. When the file does not expose explicit page boundaries, Mataba preserves exact extracted text but does not invent Word page numbers.
- TXT references identify that page metadata is unavailable.

The local vault protects stored token maps from casual plaintext inspection, but it is not a defence against same-origin script compromise/XSS or a compromised browser profile. Clearing browser storage removes the local key and token maps; the original values cannot then be rehydrated on that device.

Gemini Nano availability depends on browser/device support. If it is unavailable, the app uses local pattern screening and requires manual review; it never sends the original unredacted source text as a fallback.

## Phase 3 — evidence-grounded analysis and reports

Implemented:

- Structured output for executive summary, findings, obligations, termination overview and lawyer-style report.
- Each finding and obligation requires exact citations that are checked against submitted source text. Summary, termination and lawyer report sections also carry exact source citations.
- Unsupported findings/obligations are removed. Narrative sections with no verified citation are replaced with a clear no-evidence statement.
- Contract evidence and user reference evidence remain distinguishable by source type.
- HR reporting remains limited to Employment Agreement, Job Offer and Severance Agreement.
- HR analysis is structured into seven required topics: probation, termination notice, severance, non-compete, non-solicit, IP assignment and benefits.
- A `FOUND` HR topic without a verified citation is downgraded to jurisdictional review.
- `NOT_FOUND_IN_SUBMITTED_DOCUMENTS` is explicitly not treated as evidence that no statutory entitlement exists.
- HR topic/status labels are bilingual in the report UI.

Citation matching proves that an excerpt occurs in a submitted source. It does not independently prove legal accuracy, statutory applicability or enforceability. This remains a document-grounded analysis tool, not legal representation or counsel review.

## Backend request flow

1. The browser extracts the PDF/DOCX/TXT source locally.
2. Local Gemini Nano and deterministic patterns identify PII. The user must inspect and approve the redaction preview.
3. The browser sends only sanitized contract/reference text, Firebase ID token and App Check token to FastAPI.
4. FastAPI verifies identity and App Check, validates the request and builds the model prompt.
5. FastAPI obtains a server-side OAuth token through ADC and calls the Firebase AI Logic server prompt template in the configured location.
6. FastAPI validates the model response and verifies exact citations against the corresponding source pages.
7. The verified report returns to the browser; the browser rehydrates display text from the local encrypted token vault only.
8. Online follow-up uses the same FastAPI → Firebase AI Logic → FastAPI path. Offline follow-up uses Gemini Nano `ONLY_ON_DEVICE` with locally cached sanitized evidence.

## Repository layout

```text
mataba/
├── index.html
├── public/config.js
├── src/                          # Frontend only
│   ├── main.ts
│   ├── i18n.ts
│   ├── styles.css
│   ├── types.ts
│   └── lib/
│       ├── ai.ts                 # Gemini Nano ONLY_ON_DEVICE + backend calls
│       ├── backend.ts            # authenticated FastAPI client
│       ├── documents.ts          # PDF/DOCX/TXT extraction
│       ├── firebase.ts           # Firebase web service initialization
│       ├── localDb.ts            # Dexie/IndexedDB
│       ├── piiVault.ts           # AES-GCM local token-map storage
│       ├── privacy-utils.ts      # pure redaction functions with local tests
│       ├── redaction.ts          # local redaction orchestration
│       └── repository.ts         # Firebase data persistence
├── backend/                      # FastAPI + Firebase backend configuration
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── schemas.py
│   │   └── services/
│   │       ├── analysis.py
│   │       └── firebase_ai_logic.py
│   ├── firebase/
│   │   ├── ai_logic_templates/
│   │   ├── firestore.rules
│   │   └── storage.rules
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── scripts/
│   ├── test-privacy-utils.mjs
│   └── validate-typescript.mjs
├── docs/IMPLEMENTATION_DECISIONS.md
├── docs/PHASE_1_3_VALIDATION.md
├── firebase.json                 # Firestore/Storage rules only; no Hosting config
├── package.json
├── tsconfig.json
└── build.mjs / dev.mjs / serve.mjs
```

## Setup

### Prerequisites

- Node.js 20.19+ and npm.
- Python 3.12+.
- A Google Cloud project linked to Firebase.
- Firebase CLI and Google Cloud CLI for provisioning and rules deployment.

### Firebase project services

Configure only the services the product actually uses:

1. Firebase Authentication with the required sign-in provider.
2. Firebase App Check with reCAPTCHA Enterprise for the web app.
3. Cloud Firestore in the approved Canadian location.
4. Cloud Storage in the approved Canadian location if/when original files are added to the storage workflow.
5. Firebase AI Logic, the Agent Platform Gemini provider, and the regional server prompt templates.

The Firebase AI Logic model and template location must match. For the Canadian Gemini 3.8 Flash path, configure Provisioned Throughput for Montréal before enabling the backend flag. Server prompt templates must be created and locked in the exact intended location using Firebase's advanced template REST workflow. The source files are in `backend/firebase/ai_logic_templates/`.

### Backend

```bash
cd backend
cp .env.example .env
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Configure `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_APP_ID`, template IDs and the model/region settings. For local development, sign in to Google Application Default Credentials with an account authorized to call the Firebase AI Logic template endpoint:

```bash
gcloud auth application-default login
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Health check: `http://127.0.0.1:8080/api/health`.

For production, use a dedicated service identity with the minimum permissions required for the Firebase AI Logic server-template REST method. Do not deploy a downloaded service-account JSON key.

### Frontend

Configure `public/config.js` with the Firebase web app values and the FastAPI URL. These are public browser configuration values; never put server credentials in this file.

```bash
npm install
npm run dev
```

### Validation commands

```bash
# Frontend syntax transpilation and local privacy logic tests
npm run validate:typescript
npm run test:privacy

# Frontend full typecheck and bundle (requires npm dependencies)
npm run typecheck
npm run build

# Backend tests and template validation
cd backend
pip install -r requirements-dev.txt
pytest -q
```

The Python tests and privacy utility tests run without a live Firebase project. A live AI Logic call still requires the client's published prompt templates, valid Firebase ID/App Check tokens, ADC/service identity permissions and Montréal Provisioned Throughput configuration.

## Deployment boundaries

- **Frontend:** deploy the static `dist/` output to any static hosting provider of choice. Firebase Hosting is not required.
- **FastAPI:** deploy the Python ASGI app to an approved host. Cloud Run is one possible GCP deployment target, not a Firebase AI Logic dependency.
- **Firebase:** provision only the required backend services and security rules. `firebase.json` includes Firestore and Storage rules only; it intentionally has no Hosting block.

## Privacy and production notes

- Original uploaded contract files and reversible PII token maps are not sent to FastAPI or cloud AI.
- Only sanitized text is sent for cloud analysis after explicit user review.
- PII screening is best-effort. Users must inspect the redaction diff; this is not a guarantee that every personal identifier is detected.
- Do not log request bodies, prompts, model responses, source excerpts or token values.
- Citation verification proves text matching, not legal correctness.
- Complete security acceptance testing, browser testing and WCAG 2.2 AA verification before production launch.
