# Phase 5–6 validation — Mataba 2.9.3

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
- 320px overflow support.
- axe-core WCAG 2.2 A/AA browser scans through Python Playwright when run.

## Current application layout

- Single Python FastAPI server in `app/main.py`.
- HTML templates are stored in `app/templates/`.
- CSS and plain JavaScript modules are stored in `app/static/`.
- There is no separate frontend project, TypeScript, Node/npm build process or generated static directory.
- Root `vercel.json` includes the templates and static files in the `app/main.py` function bundle and sets the function region to Montréal (`yul1`).
- Firebase rules and prompt templates are stored under the root `firebase/` folder.

## Local acceptance commands

```bash
python -m pytest tests -q
python scripts/validate_static_assets.py
python scripts/test_privacy_utils.py
python scripts/test_browser_ux.py
```

Firebase rule checks use Python REST calls against the Auth, Firestore and Storage emulators:

```bash
firebase emulators:start --project demo-mataba-rules --only auth,firestore,storage
python scripts/test_firebase_rules.py
```

## External validation still required

Vercel deployment and live browser checks must be run in the client's project. Confirm the Function region is `yul1`, environment variables are configured, static files are served, and Firebase Admin, App Check, Firebase AI Logic template permissions and the model's Canadian processing location are valid before production.
