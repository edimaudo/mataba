# Independent legal Q&A and custom 404 validation — Mataba 2.9.1

## UX and system assumptions

- The independent Q&A page is available at `/qa` and is integrated into the signed-in Mataba navigation.
- It does not require a contract, contract ID, uploaded document or existing review.
- The initial Q&A scope is Canadian employment standards and labour legislation: one principal official statute for Canada (federally regulated workplaces) and each province/territory.
- The initial source registry does not claim to cover municipal bylaws, every regulation or other legal subject areas.
- Only a fixed allowlisted registry of official legislation URLs is fetched. Callers cannot provide arbitrary URLs.
- FastAPI retrieves relevant statute passages, invokes the existing Firebase AI Logic server-template integration, and returns citations only where the quoted text matches retrieved text.
- If the source cannot be retrieved or does not contain relevant passages, the API does not ask the model to improvise. If the model returns no verifiable citation, the answer is replaced with an insufficient-evidence response.
- Questions are checked for high-confidence residual identifiers before official-source retrieval and model inference. The UI warns users not to include names or identifying data.
- Firebase Authentication and App Check are required for online Q&A. “No contract required” does not mean anonymous access.
- Unknown browser routes return `frontend/404.html` with HTTP 404. Missing static assets return a non-HTML 404.

## Local validation completed

- Full Python test suite: **86 passed**.
- Python compilation (`compileall`): passed.
- All 12 TypeScript files passed Node's built-in TypeScript syntax parsing (`node --experimental-strip-types --check`). This checks syntax only; it is not a full TypeScript type-check or bundle.
- Vercel, Firebase and frontend package JSON parsing: passed.
- `/qa` route and standalone API tests: passed using mocked Firebase AI Logic; the request contains no contract or page fields.
- Jurisdiction registry test: federal, all provinces and territories present.
- Legal source tests: official HTML extraction/ranking and off-domain redirect rejection passed.
- Citation tests: exact official excerpt accepted; invalid/wrong-source citations suppressed and answer withheld.
- 404 tests: true HTTP 404 page returned; missing `.js` asset does not return HTML.
- Static accessibility contracts: Q&A navigation, no-contract message, privacy notice and post-submit focus target checked.

## Not yet verified

- Live downloads and extraction from every government source in the deployed Vercel runtime.
- Actual Firebase AI Logic inference using the published `mataba-legal-qa-v1` template and client-project App Check/IAM credentials.
- Production TypeScript type-check and bundle. Browser package installation/build were not run in this environment.
- Playwright/axe run of the full compiled app. An attempt to launch the local Chromium browser was blocked by the execution environment's browser policy.
- Legal corpus completeness. This initial release contains principal employment/labour statutes, not every regulation, municipal bylaw or all legal subject areas.

## Preview acceptance steps

1. Sign in and open `/qa` from the primary navigation, or navigate directly to `/qa`.
2. Select the jurisdiction where the work is performed. Select Federal only for a federally regulated workplace.
3. Ask a general question, such as “What does the legislation say about overtime?” Do not include personal identifiers.
4. Confirm the response links to the official source and includes exact verified quotations.
5. Ask about something absent from the retrieved excerpts; Mataba should return an insufficient-evidence response rather than guess.
6. Open an unknown browser route such as `/not-a-real-page`; confirm the custom page appears with HTTP 404.
7. Request a missing asset such as `/assets/not-real.js`; confirm it returns a normal 404 rather than the HTML not-found page.
