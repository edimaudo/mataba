from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from firebase_admin import initialize_app, get_app

from .config import get_settings
from .security import Identity, require_identity
from .schemas import (
    AnalyzeRequest, FollowUpRequest, VerifyAnalysisRequest, VerifyFollowUpRequest,
    AnalysisDraft, FollowUpDraft,
)
from .services.analysis import build_analysis_prompt, build_follow_up_prompt, verify_analysis, verify_follow_up
from .services.firebase_ai_logic import FirebaseAILogicError, firebase_ai_logic_http_status, generate_from_template

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.firebase_project_id:
        try:
            get_app()
        except ValueError:
            initialize_app(options={"projectId": settings.firebase_project_id})
    yield


app = FastAPI(
    title="Mataba API",
    version="2.5.0",
    description=(
        "Python application backend for Mataba. FastAPI calls Firebase AI Logic server prompt templates; "
        "Firebase provides Authentication, App Check, Firestore and Cloud Storage."
    ),
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
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


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "mataba-api",
        "environment": settings.environment,
        "aiProvider": "firebase-ai-logic-server-templates",
        "aiInferenceLocation": settings.firebase_ai_logic_location,
        "aiModel": settings.firebase_ai_logic_model,
        "aiRegionCompatible": _ai_region_compatible(),
        "aiProvisionedThroughputConfigured": settings.firebase_ai_logic_provisioned_throughput_enabled,
        "firebaseProjectConfigured": bool(settings.firebase_project_id),
        "analysisTemplateConfigured": bool(settings.firebase_ai_analysis_template_id),
        "followupTemplateConfigured": bool(settings.firebase_ai_followup_template_id),
    }


@app.post("/api/analyze")
async def analyze_contract(
    payload: AnalyzeRequest,
    identity: Identity = Depends(require_identity),
):
    reject_preview(identity)
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


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_, __):
    return JSONResponse(status_code=422, content={"detail": "The request did not match the expected Mataba API schema."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, __):
    return JSONResponse(status_code=500, content={"detail": "An unexpected API error occurred."})
