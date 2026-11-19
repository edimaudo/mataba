# Phase 5–6 validation — Mataba 2.9.1

## Security and UX implementation retained

### Phase 5
- Firebase ID token verification and revocation checks.
- App Check token verification and binding to the configured Web App ID.
- Request body limits, per-user rate limits and residual-PII checks.
- Tenant-isolated Firestore rules and Storage write restrictions.
- Reauthentication before account data deletion.
- Python route tests and Python Emulator REST tests.

### Phase 6
- Skip link and main landmark focus.
- Mobile navigation dialog semantics, focus trap, Escape close, inert background and focus restoration.
- Report tabs and keyboard navigation.
- EN/FR navigation, font sizes, light/dark themes and responsive breakpoints.
- 320px overflow checks.
- axe-core WCAG 2.2 A/AA scans through Python Playwright.

## Vercel/source-layout changes

- Removed the redundant top-level `backend/` directory; Python modules now live in the standard `app/` package.
- Root `vercel.json` configures the `app/main.py` FastAPI Function in Montréal (`yul1`), build command, function file inclusion/exclusion and security/cache headers.
- Root `requirements.txt` and `requirements-dev.txt` declare Python dependencies.
- Python build script generates `public/`, which Vercel serves through its CDN.
- Firebase rules and prompt templates are stored under the root `firebase/` folder.
- The same app routes and frontend asset URLs are retained.

## Local acceptance commands

```bash
python -m pytest tests -q
python scripts/validate_frontend.py
python scripts/test_privacy_utils.py
python scripts/test_browser_ux.py
```

Firebase rule checks use Python REST calls against the Auth, Firestore and Storage emulators:

```bash
firebase emulators:start --project demo-mataba-rules --only auth,firestore,storage
python scripts/test_firebase_rules.py
```

## External validation still required

Vercel CLI/build deployment and live browser checks must be run in the Vercel project. Confirm the Function region is `yul1`, the project root is the repository root, and environment variables are configured. Validate Firebase Admin authentication, App Check, Firebase AI Logic template permissions and the model's Canadian region/consumption mode in the client's staging project before production.
