import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

ALGORITHM = "HS256"

_bearer = HTTPBearer(auto_error=False)


def is_authorized_admin(email: str) -> bool:
    """Allowlisted Google account, or the dev-fallback credential identity."""
    normalized = email.lower()
    return (
        normalized in settings.admin_allowed_email_set
        or normalized == settings.admin_email.lower()
    )


def verify_admin_credentials(email: str, password: str) -> bool:
    email_ok = secrets.compare_digest(email.encode(), settings.admin_email.encode())
    password_ok = secrets.compare_digest(password.encode(), settings.admin_password.encode())
    return email_ok and password_ok


def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency guarding internal endpoints. Returns the authenticated subject."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    subject = payload["sub"]
    # Re-checked on every request (not just at login) so removing an email from the
    # allowlist locks that account out immediately, even with a still-valid token.
    if not is_authorized_admin(subject):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized for the admin dashboard",
        )
    return subject
