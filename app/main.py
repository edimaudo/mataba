from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from pathlib import Path
from .config import get_settings
from .security import Identity, require_identity
from .rate_limit import user_rate_limiter
from .schemas import (
    AnalyzeRequest, FollowUpRequest, VerifyAnalysisRequest, VerifyFollowUpRequest,
    AnalysisDraft, FollowUpDraft, LegalQARequest, LegalQADraft,
)
from .services.analysis import build_analysis_prompt, build_follow_up_prompt, verify_analysis, verify_follow_up
from .services.firebase_ai_logic import FirebaseAILogicError, firebase_ai_logic_http_status, generate_from_template
from .services.privacy_guard import require_sanitized_text
from .services.legal_sources import LAW_SOURCES, LAWYER_DIRECTORIES, retrieve_law_passages
from .services.legal_qa import build_legal_qa_prompt, verify_legal_qa

settings = get_settings()
APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


app = FastAPI(
    title="Mataba",
    version="2.9.8",
    description=(
        "Python FastAPI application serving Mataba's pages, static JavaScript and API routes. "
        "Firebase AI Logic is the cloud inference integration."
    ),
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
class RequestBodyLimitMiddleware:
    """Bound request bodies before FastAPI parses potentially large JSON payloads."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") not in {"/api/analyze", "/api/follow-up", "/api/legal-qa"}:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return

        messages = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            messages.append(message)
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                await self._reject(send)
                return
            if not message.get("more_body", False):
                break

        index = 0

        async def replay_receive():
            nonlocal index
            if index < len(messages):
                current = messages[index]
                index += 1
                return current
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(send):
        body = b'{"detail":"The request exceeds the API request-size limit."}'
        await send({"type": "http.response.start", "status": 413, "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]})
        await send({"type": "http.response.body", "body": body})


app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_api_request_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
)


def reject_preview(identity: Identity) -> None:
    if identity.uid == "preview":
        raise HTTPException(status_code=403, detail="Local preview accounts cannot access cloud analysis.")


def raise_ai_error(exc: FirebaseAILogicError) -> HTTPException:
    return HTTPException(status_code=firebase_ai_logic_http_status(exc), detail=str(exc))


def _ai_region_compatible() -> bool:
    try:
        from .services.firebase_ai_logic import validate_model_location
        validate_model_location(
            settings.firebase_ai_logic_model,
            settings.firebase_ai_logic_location,
            settings.firebase_ai_logic_provisioned_throughput_enabled,
        )
        return True
    except FirebaseAILogicError:
        return False


def enforce_user_limit(identity: Identity, action: str) -> None:
    limits = {"analysis": settings.analysis_requests_per_minute, "follow-up": settings.followup_requests_per_minute, "legal-qa": settings.legal_qa_requests_per_minute}
    limit = limits.get(action, 0)
    user_rate_limiter.check(identity.uid, action, limit)


@app.get("/api/health")
async def health():
    # Public liveness endpoint: do not disclose project, template, model or
    # regional processing settings to unauthenticated callers.
    return {"status": "ok", "service": "mataba-api"}


@app.post("/api/analyze")
async def analyze_contract(
    payload: AnalyzeRequest,
    identity: Identity = Depends(require_identity),
):
    reject_preview(identity)
    enforce_user_limit(identity, "analysis")
    require_sanitized_text(
        (page.text for page in [*payload.contractPages, *payload.referencePages]),
        payload.language,
    )
    try:
        prompt = build_analysis_prompt(payload)
        draft_data = await generate_from_template(
            template_id=settings.firebase_ai_analysis_template_id,
            prompt=prompt,
            app_check_token=identity.app_check_token or "",
            settings=settings,
        )
        draft = AnalysisDraft.model_validate(draft_data)
        verified = verify_analysis(VerifyAnalysisRequest(
            contractType=payload.contractType,
            language=payload.language,
            contractPages=payload.contractPages,
            referencePages=payload.referencePages,
            draft=draft,
        ))
        return verified.model_dump(mode="json")
    except FirebaseAILogicError as exc:
        raise raise_ai_error(exc) from exc
    except ValidationError as exc:
        # Do not include model text or source text in logs or client errors.
        raise HTTPException(status_code=502, detail="Firebase AI Logic returned a report that did not match Mataba's required structure. Please retry.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The contract could not be analyzed.") from exc


@app.post("/api/follow-up")
async def answer_follow_up(
    payload: FollowUpRequest,
    identity: Identity = Depends(require_identity),
):
    reject_preview(identity)
    enforce_user_limit(identity, "follow-up")
    require_sanitized_text((page.text for page in payload.pages), payload.language)
    try:
        prompt = build_follow_up_prompt(payload)
        draft_data = await generate_from_template(
            template_id=settings.firebase_ai_followup_template_id,
            prompt=prompt,
            app_check_token=identity.app_check_token or "",
            settings=settings,
        )
        draft = FollowUpDraft.model_validate(draft_data)
        verified = verify_follow_up(VerifyFollowUpRequest(
            question=payload.question,
            language=payload.language,
            pages=payload.pages,
            draft=draft,
        ))
        return verified.model_dump(mode="json")
    except FirebaseAILogicError as exc:
        raise raise_ai_error(exc) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Firebase AI Logic returned an answer that did not match Mataba's required structure. Please retry.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The follow-up question could not be answered.") from exc


@app.get("/api/legal-qa/jurisdictions")
async def legal_qa_jurisdictions(identity: Identity = Depends(require_identity)):
    """Return the supported employment/labour law jurisdictions and official source titles."""
    return [
        {"code": source.code, "jurisdiction": source.jurisdiction, "level": source.level, "actTitle": source.act_title, "officialUrl": source.official_url}
        for source in LAW_SOURCES.values()
    ]


@app.get("/api/legal-qa/lawyer-directories")
async def legal_qa_lawyer_directories(identity: Identity = Depends(require_identity)):
    """Return curated law-society directories for finding employment-law counsel."""
    return [
        {"code": code, **directory}
        for code, directory in LAWYER_DIRECTORIES.items()
    ]


@app.post("/api/legal-qa")
async def answer_legal_question(
    payload: LegalQARequest,
    identity: Identity = Depends(require_identity),
):
    """Answer an independent law question without requiring a contract or uploaded document."""
    reject_preview(identity)
    enforce_user_limit(identity, "legal-qa")
    require_sanitized_text([payload.question], payload.language)
    try:
        source, passages = await retrieve_law_passages(
            payload.jurisdictionCode,
            payload.question,
            municipality_name=payload.municipalityName,
            law_type=payload.lawType,
        )
        prompt = build_legal_qa_prompt(payload, source, passages)
        draft_data = await generate_from_template(
            template_id=settings.firebase_ai_legal_qa_template_id,
            prompt=prompt,
            app_check_token=identity.app_check_token or "",
            settings=settings,
        )
        draft = LegalQADraft.model_validate(draft_data)
        verified = verify_legal_qa(payload, source, passages, draft)
        return verified.model_dump(mode="json")
    except FirebaseAILogicError as exc:
        raise raise_ai_error(exc) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Firebase AI Logic returned an answer that did not match Mataba's required structure. Please retry.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The legal question could not be answered.") from exc


@app.get("/", include_in_schema=False)
async def landing_page():
    """Public Mataba landing page."""
    page = TEMPLATES_DIR / "landing.html"
    if not page.is_file():
        raise HTTPException(status_code=503, detail="Mataba landing page is missing.")
    return FileResponse(page, media_type="text/html; charset=utf-8")


@app.get("/signin", include_in_schema=False)
async def legacy_signin_redirect():
    """Keep old bookmarks working without exposing a sign-in page."""
    return RedirectResponse(url="/app", status_code=307)


@app.get("/app", include_in_schema=False)
@app.get("/qa", include_in_schema=False)
async def application_page():
    """Serve the application shell directly; the browser establishes a guest session."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=503, detail="Mataba application template is missing.")
    return FileResponse(index_file, media_type="text/html; charset=utf-8")


@app.get("/{asset_path:path}", include_in_schema=False)
async def static_assets(asset_path: str):
    """Serve browser assets directly from app/static; no frontend build is required."""
    if asset_path == "api" or asset_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    root = STATIC_DIR.resolve()
    candidate = (root / asset_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=404, detail="Not found")
    if candidate.is_file():
        return FileResponse(candidate)

    # Unknown application routes receive a real HTTP 404 page. Missing asset
    # paths remain a plain 404 so clients never parse HTML as JS or CSS.
    if asset_path and "." not in Path(asset_path).name:
        not_found = TEMPLATES_DIR / "404.html"
        if not_found.is_file():
            return FileResponse(not_found, status_code=404, media_type="text/html; charset=utf-8")
    raise HTTPException(status_code=404, detail="Not found")


@app.middleware("http")
async def api_security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_, __):
    return JSONResponse(status_code=422, content={"detail": "The request did not match the expected Mataba API schema."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, __):
    return JSONResponse(status_code=500, content={"detail": "An unexpected API error occurred."})
