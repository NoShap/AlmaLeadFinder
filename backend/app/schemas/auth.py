from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str  # Google ID token from the Sign in with Google button


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
