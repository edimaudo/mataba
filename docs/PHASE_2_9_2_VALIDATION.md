# Mataba 2.9.2 validation — municipal jurisdiction support

## Implemented

- Legal Q&A retains **Employment law** as its only law-type option.
- Jurisdiction selection supports Federal, Province/Territory and Municipal scopes.
- Municipal scope requires a municipality name and its parent province or territory.
- The FastAPI request schema validates the hierarchy and carries the municipality into source resolution, the Firebase AI Logic prompt and response metadata.
- Every registered legislation source records its actual level: federal, provincial, territorial or municipal.
- A curated municipal registry resolves exact matches on parent jurisdiction, normalized municipality and law type. Only code-configured official URLs are eligible; callers cannot provide arbitrary URLs.
- If no municipal source is registered, the parent employment statute is used and identified as provincial/territorial rather than municipal.
- English and French labels, explanatory text and source-level metadata are included.

## Current source-coverage limitation

The municipal registry has no entries for Employment law in this release. Municipal selection therefore adds local context, but does not by itself retrieve municipal bylaws. A verified municipal source must be registered for the relevant municipality and law type before it can be cited. The system does not present a provincial or territorial statute as a municipal bylaw.

## Validation results

- Python test suite: **97 passed**.
- Python compilation (`compileall`): passed.
- TypeScript syntax parsing: all files under `frontend/src/*.ts` passed Node's TypeScript syntax check. This is syntax validation, not a complete type-check.
- JSON configuration parsing: `frontend/package.json`, `vercel.json` and `firebase.json` passed.
- Municipal source resolution, parent-jurisdiction matching, API request flow, prompt context and response source-level metadata are covered by automated tests.

## Not run

- Full TypeScript type-check and production frontend bundle: not completed because frontend dependencies were not installed; the package installation attempt timed out.
- Browser interaction and axe accessibility tests: not run because the frontend bundle and browser test dependencies were unavailable.
- Live Firebase AI Logic inference and live downloads from official municipal sources: not run. Municipal employment-law source entries are not configured in this release.
