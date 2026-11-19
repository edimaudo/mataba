# Standalone legal Q&A and custom 404 validation — Mataba 2.9.1

## UX and system assumptions

- Legal Q&A is a separate authenticated page at `/qa`.
- It does not require a contract, contract ID or uploaded file.
- The first release is limited to Canadian employment standards/labour legislation: one official principal statute for Canada (federally regulated workplaces) and each province/territory.
- The first release does not claim coverage of municipal bylaws, all regulations or other legal subject areas.
- Only a fixed allowlisted registry of official legislation URLs is fetched. Users cannot provide arbitrary URLs.
- The backend retrieves relevant passages, uses the existing Firebase AI Logic server template, and returns citations only when the quoted text matches the retrieved official source.
- User questions are checked for high-confidence residual identifiers before official-law retrieval or model invocation.
- The page remains behind Firebase Authentication and App Check. “No contract required” does not mean anonymous access.
- Unknown browser routes return `frontend/404.html` with HTTP 404 from FastAPI. Missing static assets return a non-HTML 404.

## Local validation completed

- Python backend suite: 86 passed.
- Python compilation: passed.
- TypeScript syntax parsing for all 12 `.ts` files using Node's built-in TypeScript stripping/check mode: passed.
- Vercel, Firebase and frontend package JSON parsing: passed.
- `/qa` route and standalone API tests: passed (mock Firebase AI Logic, no contract fields supplied).
- Citation matching: valid official excerpt accepted; invented/wrong-source citation suppressed.
- Redirect allowlist test: redirect outside the official source domain rejected.
- 404 route tests: true HTTP 404 page returned; missing `.js` asset does not return HTML.
- Static accessibility checks: page labels, no-contract message and post-submit focus target verified.

## Not yet verified

- Live download and extraction from each of the 14 government legislation sources in Vercel's runtime.
- Actual Firebase AI Logic execution using the published `mataba-legal-qa-v1` template and the client's App Check/IAM credentials.
- Browser-level Playwright/axe execution against a production bundle; frontend dependency installation and bundling are still required.
- Legal content completeness. This initial registry provides principal employment/labour statutes, not every regulation, municipal bylaw or all legal subject areas.

## How to test in Preview

1. Open `/qa` while signed in.
2. Select the jurisdiction where the work is performed. Select Federal only for a federally regulated workplace.
3. Ask a general question such as “What does the legislation say about overtime?” Do not include names or personal identifiers.
4. Confirm the response links to the official source and includes exact verified quotations.
5. Ask something not addressed in the retrieved excerpts; the system should say evidence is insufficient instead of guessing.
6. Open a non-existent path such as `/not-a-real-page`; confirm the custom page appears with HTTP 404.
7. Request a missing asset such as `/assets/not-real.js`; confirm it returns a normal 404 rather than the HTML not-found page.
