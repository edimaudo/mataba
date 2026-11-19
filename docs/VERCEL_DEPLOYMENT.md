# Deploy Mataba to Vercel

The project is a single FastAPI application. Vercel detects `app/main.py`; there is no `backend/` project root and no separate API service.

## Included configuration

The repository-root `vercel.json` configures:

- FastAPI entrypoint: `app/main.py`.
- Function region: `yul1` (Montréal).
- Build command: install the browser dependencies and run the Python TypeScript build script.
- Include the Firebase AI Logic prompt templates and generated `public/` assets in the function bundle.
- Exclude tests, scripts, frontend source and installed packages from the deployed Python function.
- `Cache-Control: no-store` on API responses and default security headers.

Vercel automatically serves files in root `public/` through its CDN. The application build creates that directory from `frontend/`.

## Deploy through the Vercel dashboard

1. Push the repository to the client's Git provider.
2. Import the repository in Vercel.
3. Leave **Root Directory** set to the repository root.
4. Vercel detects the FastAPI app at `app/main.py`.
5. Add the variables from `.env.example` in **Project → Settings → Environment Variables**.
6. Set `ENVIRONMENT=production`.
7. Set `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` to the base64 value of the Google service-account JSON. Mark it as sensitive. Do not use a client-side config file for this credential.
8. Confirm the Function Region is `yul1` (Montréal). The checked-in `vercel.json` also sets this value.
9. Deploy a Preview and test the frontend, the custom `/404.html` response, `/qa`, `/api/health`, sign-in, App Check, official-law retrieval and a staging Firebase AI Logic request using the `mataba-legal-qa-v1` template.
10. Deploy to Production only after regional inference and privacy checks pass.

## Create the service-account environment value

On macOS/Linux:

```bash
base64 < service-account.json | tr -d '\n'
```

Copy the output into the sensitive Vercel environment variable `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`. Do not commit `service-account.json` or the encoded value.

The service account must have only the permissions required for Firebase Admin token/App Check verification and the Firebase AI Logic server prompt-template call. Follow the client's IAM policy and least-privilege requirements.

## Deploy with Vercel CLI

The Vercel CLI is an external deployment tool, not part of Mataba's runtime. Install and authenticate it according to Vercel's current instructions. Then run from the repository root:

```bash
vercel link
vercel deploy
```

After Preview acceptance:

```bash
vercel deploy --prod
```

## Regional-processing distinction

`yul1` configures the Vercel FastAPI Function to execute in Montréal. Firebase AI Logic separately uses `northamerica-northeast1`. Both regional settings must be checked in the live project. Static assets in `public/` are delivered by Vercel's global CDN; no contract text or customer records are stored in those static assets.
