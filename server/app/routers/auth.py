from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_access_token, verify_password
from ..deps import get_db
from ..models import User
from ..schemas import Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login with User ID (username field) + password; returns a JWT."""
    user = db.scalar(select(User).where(User.user_id == form.username))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID or password",
        )
    token = create_access_token(user_id=user.user_id, role=user.role)
    return Token(access_token=token, user_id=user.user_id, role=user.role)
