# Mataba implementation decisions — 2.5.0 (Phases 1–3)

## Confirmed user architecture

- Frontend: vanilla HTML, vanilla CSS and TypeScript only.
- Backend: Python + FastAPI together with Firebase backend services.
- AI integration: Firebase AI Logic is the exclusive Gemini integration for cloud and supported on-device tasks.
- No React, Tailwind, Vite, JSX, Google Gen AI Python SDK, Vertex AI Python SDK or direct model-generation client.
- Firebase Hosting is not required; frontend hosting is independent.
- Phase 4 (additional library/folder management) is excluded from this implementation request.

## Backend and AI boundary

Online requests follow:

`Browser → FastAPI → Firebase AI Logic server prompt template → FastAPI → Browser`

FastAPI verifies the user's Firebase Authentication ID token and App Check token. It validates the request and builds the prompt. The server-to-server call to Firebase AI Logic uses Application Default Credentials with the required `cloud-platform` OAuth scope. The user's ID token is not used as the service-to-service OAuth credential.

The service hostname for the documented Firebase AI Logic REST template method is `firebasevertexai.googleapis.com`; this is the Firebase AI Logic REST API, not a direct Vertex AI SDK or model endpoint.

The browser uses Firebase web SDK services for authentication and user-scoped Firebase data access where required by the product. The browser's Firebase AI Logic instance is used only with `InferenceMode.ONLY_ON_DEVICE` for Gemini Nano. It has no cloud fallback.

## Canadian model region

The configured cloud model is `gemini-3.8-flash` in `northamerica-northeast1` (Montréal). As of 2026-11-16, Google documents in-region ML processing for this model in Montréal with Provisioned Throughput. Standard PayGo is listed for global, US and EU, not Montréal. The backend therefore defaults `FIREBASE_AI_LOGIC_PROVISIONED_THROUGHPUT_ENABLED=false` and rejects cloud inference until the project operator has provisioned and verified Canadian capacity. Setting the flag to true is an explicit operator assertion, not a programmatic proof of purchased throughput.

Firebase AI Logic server prompt templates are a Preview feature and have no SLA. The exact server-template lifecycle and regional route must pass a live staging test before production.

## Phase 2 privacy boundary

- Document extraction, privacy screening and masking occur in the browser.
- Gemini Nano calls use `ONLY_ON_DEVICE`; pattern/manual screening is the fallback.
- Every 9-digit SIN candidate is masked, whether or not its Luhn checksum is valid. The checksum helper is diagnostic only.
- Token namespaces are unique per source document to avoid contract/reference token collisions.
- Reversible PII maps are AES-GCM encrypted in IndexedDB under a non-extractable Web Crypto key. They are not sent to FastAPI, Firestore, Storage or Firebase AI Logic.
- This local vault is not a defence against same-origin XSS or a compromised browser profile. Browser data clearing destroys the local key and mapping.
- PDF page indices are retained. DOCX page indices are taken only from explicit page-break metadata; no inferred Word pagination is invented.

## Phase 3 evidence boundary

- Findings and obligations require exact source excerpts.
- Executive summary, termination overview and lawyer-style report include section-level verified citations.
- Each of the seven HR areas is separately structured and has its own citation list and status.
- A `FOUND` HR topic without evidence is downgraded to `REQUIRES_JURISDICTIONAL_REVIEW`.
- Absence from submitted documents is never represented as absence of statutory rights.
- Citation verification establishes exact text presence only. It does not establish legal accuracy, jurisdictional applicability or enforceability.

## Excluded / deferred phases

- Phase 4: excluded at the user's direction; no additional folder/library functionality was added.
- Phase 5: security acceptance testing remains next.
- Phase 6: browser, accessibility and full UX validation remains next.
