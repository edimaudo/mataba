from dataclasses import dataclass
from fastapi import Header, HTTPException, status
import firebase_admin
from firebase_admin import app_check, auth
from firebase_admin.exceptions import FirebaseError
import jwt

from .config import get_settings


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str | None
    firebase_id_token: str
    app_check_token: str | None


def _firebase_app():
    settings = get_settings()
    if not settings.firebase_project_id:
        raise HTTPException(status_code=503, detail="Firebase project is not configured on the API.")
    try:
        return firebase_admin.get_app()
    except ValueError:
        try:
            return firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        except ValueError:
            return firebase_admin.get_app()


async def require_identity(
    authorization: str | None = Header(default=None, alias="Authorization"),
    app_check_token: str | None = Header(default=None, alias="X-Firebase-AppCheck"),
) -> Identity:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid Firebase sign-in is required.")

    settings = get_settings()
    firebase_app = _firebase_app()
    token = authorization[7:].strip()
    try:
        decoded = auth.verify_id_token(
            token,
            app=firebase_app,
            check_revoked=settings.check_revoked_firebase_tokens,
        )
    except (ValueError, auth.InvalidIdTokenError, auth.ExpiredIdTokenError, auth.RevokedIdTokenError, auth.UserDisabledError) as exc:
        raise HTTPException(status_code=401, detail="Your sign-in has expired. Sign in again.") from exc
    except FirebaseError as exc:
        raise HTTPException(status_code=503, detail="Firebase authentication could not be verified.") from exc

    if settings.require_app_check:
        if not app_check_token:
            raise HTTPException(status_code=401, detail="Firebase App Check token is required.")
        try:
            app_check.verify_token(app_check_token)
        except (ValueError, jwt.exceptions.DecodeError) as exc:
            raise HTTPException(status_code=401, detail="Firebase App Check verification failed.") from exc
        except FirebaseError as exc:
            raise HTTPException(status_code=503, detail="Firebase App Check could not be verified.") from exc

    return Identity(
        uid=str(decoded["uid"]),
        email=decoded.get("email"),
        firebase_id_token=token,
        app_check_token=app_check_token,
    )
