# Phase 1–3 implementation notes — Mataba 2.9.1

The source-layout and Vercel deployment update preserves the Phase 1–3 application behavior.

## Phase 1 — Firebase AI Logic

- FastAPI remains responsible for online analysis and follow-up routes.
- Cloud inference continues through Firebase AI Logic server prompt templates.
- Firebase ID token and App Check checks remain in the Python API.
- Region/model/consumption incompatibility continues to fail closed.
- No direct Vertex AI or Google Gen AI Python model client has been introduced.

## Phase 2 — privacy and document processing

- PDF/DOCX/TXT extraction remains in the browser.
- Gemini Nano runs only in on-device mode where available.
- Pattern detection and manual redaction remain available as fallbacks.
- Reversible PII mappings remain encrypted in IndexedDB and are not sent to FastAPI.
- Per-document namespaces prevent contract/reference token collisions.
- PDF page numbers and explicit DOCX page-break metadata are preserved; visual pagination is not fabricated.

## Phase 3 — analysis and reports

- Structured contract analysis, obligations and termination analysis remain in FastAPI/Firebase AI Logic.
- Contract and user-reference evidence remain distinct.
- Citation verification checks excerpts against submitted sources.
- HR report gating remains limited to employment agreements, job offers and severance agreements.
- Seven structured HR topics remain present.
- Unsupported claims remain marked for review rather than presented as verified legal conclusions.

The change removes the `backend/` directory by moving its Python package to the standard Vercel-supported `app/` package, with `app/main.py` as the entrypoint. It does not change these features or their logic.
