# Deploy Mataba to Vercel

Mataba is a single Python + FastAPI application. Its HTML templates, CSS and native JavaScript files live inside `app/` and are served by FastAPI. There is no separate frontend project or build command.

## Included configuration

The repository-root `vercel.json` configures:

- FastAPI application: `app/main.py`.
- Function region: Montréal (`yul1`).
- Inclusion of `app/templates/**`, `app/static/**` and `firebase/ai_logic_templates/**` in the function bundle.
- Exclusion of tests, scripts and documentation from the deployed function bundle.
- `Cache-Control: no-store` on API responses and baseline response security headers.

There is no Node.js/npm step and no generated static directory.

## Deploy through the Vercel dashboard

1. Push the repository to the client's Git provider.
2. Import the repository in Vercel.
3. Leave **Root Directory** set to the repository root.
4. Configure the variables from `.env.example` in **Project → Settings → Environment Variables**.
5. Set `ENVIRONMENT=production`.
6. Set `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` to the base64-encoded service-account JSON. Mark it as sensitive. Never place this credential in `app/static/config.js`.
7. Confirm that the Function Region is `yul1` (Montréal).
8. Deploy a Preview and test `/`, `/qa`, `/api/health`, the custom 404 behavior, authentication, App Check, official-law retrieval and a staging Firebase AI Logic request.
9. Promote to Production only after regional inference and privacy checks pass.

## Create the service-account environment value

On macOS/Linux:

```bash
base64 < service-account.json | tr -d '\n'
```

Copy the output into the sensitive Vercel environment variable `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`. Do not commit `service-account.json` or the encoded value.

The service account must have only the permissions required for Firebase Admin token/App Check verification and the Firebase AI Logic server prompt-template call. Follow the client's IAM policy and least-privilege requirements.

## Deploy with Vercel CLI

The Vercel CLI is an external deployment tool, not part of Mataba's runtime. Install and authenticate it separately, then run from the repository root:

```bash
vercel link
vercel deploy
```

After Preview acceptance:

```bash
vercel deploy --prod
```

## Regional-processing distinction

`yul1` configures the Vercel FastAPI Function to execute in Montréal. Firebase AI Logic separately uses its configured model location. Both must be checked in the live project. Browser libraries are loaded from the fixed CDN URLs listed in `app/templates/index.html`; contract text and customer records are not placed in those public scripts or stylesheets.
