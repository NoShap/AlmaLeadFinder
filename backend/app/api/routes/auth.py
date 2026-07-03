from fastapi import APIRouter, HTTPException, status

from app.core.security import create_access_token, verify_admin_credentials
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    if not verify_admin_credentials(body.email, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return TokenResponse(access_token=create_access_token(subject=body.email))
