# Mataba 2.9.3 validation — Python-only application and native JavaScript

## Architecture changes

- Moved the page templates into `app/templates/`.
- Moved stylesheets, configuration and browser modules into `app/static/`.
- Converted the browser source from TypeScript to ordinary JavaScript modules.
- Removed the `frontend/` directory, every `.ts` source file, the package manifest, the npm build command, the Python/esbuild build script and the generated `public/` directory.
- FastAPI now serves the HTML and static files directly from the application package.
- The development runner starts only Uvicorn/FastAPI.
- Vercel includes the application templates and static assets in the Python function bundle; there is no frontend build command.
- Existing contract analysis, PDF/DOCX/TXT extraction, upload/paste workflows, bilingual interface, local privacy processing, Firebase flows and municipal Legal Q&A were retained.

## Local validation

- Python test suite: **99 passed**.
- Python compilation (`compileall`): passed.
- All 12 native JavaScript modules passed syntax parsing. A direct privacy-helper check also passed. Node was used only as a local validation tool; it is not required by the app or deployment.
- Static application validation: passed. It confirms required files are present and that there is no `frontend/` folder, TypeScript source, package manifest or build output.
- Vercel and Firebase JSON configuration: valid.
- FastAPI serving checks: HTML, CSS, JavaScript, runtime configuration and unknown-route handling passed through the API test client.
- Manual HTTP check: `/`, `/api/health` and `/js/main.js` returned successful responses from the FastAPI server.
- Browser interaction and axe-core checks were not completed. Chromium navigation was blocked by the execution environment with `ERR_BLOCKED_BY_ADMINISTRATOR`.
- Live CDN loading for the pinned Firebase, PDF.js, Mammoth, Dexie and fflate modules was not verified here because outbound network access is unavailable.

## Runtime dependency note

Browser-only libraries are pinned in the import map/script tags in `app/templates/index.html` and are fetched by the browser. They do not introduce a Node.js or npm runtime dependency. The Python server and Python package environment remain the only application runtime/build requirements.

## External checks

Live Firebase authentication, App Check, Firebase AI Logic inference, model-region compatibility and production browser/CDN loading require the client's staging project and deployment environment.
