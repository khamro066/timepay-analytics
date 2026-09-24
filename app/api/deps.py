from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services.elevated_session_service import touch_and_check

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise credentials_exception

    username = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    return user


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_elevated_session(current_user: User = Depends(require_admin_user)) -> User:
    """A valid regular admin JWT alone is not enough here — the caller must
    have separately re-entered their password via POST /api/auth/elevate
    within the last DEFAULT_INACTIVITY_MINUTES. Used to gate sensitive
    tools like attendance corrections behind step-up re-authentication."""
    if not touch_and_check(current_user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Elevated session required or expired")
    return current_user
