from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.services.elevated_session_service import DEFAULT_INACTIVITY_MINUTES, start_elevated_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token({"sub": user.username})
    return TokenResponse(access_token=token)


class ElevateRequest(BaseModel):
    password: str


@router.post("/elevate")
def elevate(payload: ElevateRequest, current_user: User = Depends(require_admin_user)):
    """Step-up re-authentication: re-verifies the already-logged-in admin's
    password (no username needed — it comes from their existing JWT) and,
    if correct, opens a short elevated window used to gate sensitive tools
    like attendance corrections. See require_elevated_session."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    start_elevated_session(current_user.username)
    return {"elevated": True, "expires_in_minutes": DEFAULT_INACTIVITY_MINUTES}
