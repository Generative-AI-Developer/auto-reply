from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..config import get_settings
from ..deps import get_db, require_admin
from ..models import User
from ..schemas import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])
settings = get_settings()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Admin: register a user (User ID + Zone/Section + password) and create its folder."""
    if db.scalar(select(User).where(User.user_id == payload.user_id)):
        raise HTTPException(status_code=409, detail="User ID already exists")

    user = User(
        user_id=payload.user_id,
        zone_section=payload.zone_section,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    (Path(settings.main_dir) / user.user_id).mkdir(parents=True, exist_ok=True)
    return user


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())
