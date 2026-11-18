# Mataba 2.5.0 — Phase 1–3 validation record

Validation performed against the source in this package on 2026-11-16.

## Phase 1 — Firebase AI Logic

### Implemented

- FastAPI is the online AI gateway; the browser does not call cloud Gemini directly.
- FastAPI verifies Firebase Authentication ID tokens and Firebase App Check tokens before cloud analysis.
- The Python service calls the Firebase AI Logic server prompt-template REST method using Application Default Credentials with the documented `cloud-platform` OAuth scope.
- Contract-analysis and follow-up templates are stored as Dotprompt source files with YAML frontmatter and JSON output schemas.
- Model/location/consumption-mode validation blocks undocumented routes instead of falling back to global or US processing.
- Montréal Gemini 3.8 Flash processing is enabled only when the operator explicitly asserts that Provisioned Throughput is configured. This flag must remain false until the client project has provisioned and verified that capacity.

### Local validation

- Backend request method, URL, input body and required authentication headers tested with an HTTP mock.
- Missing App Check rejected before network dispatch.
- Missing template and upstream errors handled with sanitized errors.
- Montréal without Provisioned Throughput is blocked before network dispatch.
- Montréal with the explicit Provisioned Throughput setting passes the local configuration gate.
- Both prompt files parsed as YAML and checked for required input/output fields.

### Not validated against the client project

- Templates have not been created, published and locked in the client's Firebase project.
- No live request has been executed with the client's OAuth service identity, Firebase ID token and App Check token.
- The backend cannot verify that Provisioned Throughput was purchased. The environment flag is an operator assertion; confirm it in the client project before enabling it.
- Firebase AI Logic server prompt templates are Preview and should be treated as a staging gate.

## Phase 2 — privacy and document processing

### Implemented

- Pattern-based PII screening masks all nine-digit SIN candidates regardless of checksum result.
- Gemini Nano is requested with `InferenceMode.ONLY_ON_DEVICE`; if it cannot run locally, the code does not fall back to cloud inference.
- Manual redaction values enter the same tokenization path.
- Document-specific token namespaces prevent contract/reference token collisions.
- Reversible token maps are encrypted using AES-GCM and stored in IndexedDB with a non-extractable CryptoKey. The vault is local-only and is not included in backend/Firebase payloads.
- PDF page numbers are retained. DOCX page numbers are assigned only from explicit Word page-break metadata; unpaginated DOCX and TXT files do not receive invented page numbers.

### Local validation

- 14 deterministic assertions passed for valid/invalid SIN checksum candidates, PII pattern categories, namespacing, token-map values and raw-value removal from sanitized text.
- TypeScript source syntax transpilation passed for all 12 `.ts` files.

### Not validated in a real browser/device

- AES-GCM IndexedDB persistence and CryptoKey structured cloning have not yet been exercised across real browser restarts/devices.
- Gemini Nano download, model readiness, actual PII detection quality and offline question-answering require a supported desktop Chrome device and user-triggered model initialization.
- DOCX page-break extraction needs sample-file comparison against Word rendering; explicit page-break markers do not guarantee that every Word layout pagination boundary can be recovered.

## Phase 3 — evidence-grounded analysis and reports

### Implemented

- Structured contract-analysis output for executive summary, findings, obligations, termination overview and lawyer-style report.
- Exact source-excerpt matching for report sections, findings and obligations.
- Unsupported findings and obligations are omitted; narrative sections without verified citations receive a no-evidence statement.
- HR reports remain gated to Employment Agreement, Job Offer and Severance Agreement.
- Seven HR topics are required: probation, termination notice, severance, non-compete, non-solicit, IP assignment and benefits.
- Unsupported `FOUND` HR topics are downgraded to jurisdictional review; absence from uploaded documents is not presented as absence of statutory entitlement.
- Report UI renders section-level citations and bilingual HR topic/status labels.

### Local validation

- Backend tests cover evidence normalization, citation matching/rejection, report section evidence, HR topic coverage/status behavior and follow-up citation validation.
- All 18 backend tests passed.
- TypeScript source syntax transpilation passed for all 12 `.ts` files after the report UI changes.

### Limitations

- Citation verification establishes that the excerpt exists in the selected source page. It does not independently establish legal accuracy, legal applicability, or enforceability.
- Legal claims are not being compared against a separate authoritative Canadian legislation knowledge base in this phase.
- Model output quality and report layout still need client-project and browser end-to-end testing.

## Test commands

```bash
# from project root (after npm install)
npm run validate:typescript
npm run test:privacy

# full compiler/bundler checks (after npm install)
npm run typecheck
npm run build

# from backend/ (after pip install -r requirements-dev.txt)
pytest -q
```

## Phase status

| Phase | Code status | Local logic/source validation | Live/browser validation |
|---|---|---|---|
| 1 — Firebase AI Logic | Implemented | Passed | Requires client Firebase project and configured templates/capacity |
| 2 — Privacy/document processing | Implemented | Passed | Requires real browser/device and sample document QA |
| 3 — Analysis/reporting | Implemented | Passed | Requires live model and browser end-to-end QA |
| 4 — More folder/library features | Excluded at user direction | Not applicable | Not applicable |
| 5 — Security acceptance testing | Not started | Not applicable | Next phase |
| 6 — Browser/accessibility/full UX validation | Not started | Syntax checks only are not full UX QA | Next phase |
