"""Create (or ensure) the bootstrap admin user and its storage folder.

Run once after setting up the DB:  python seed_admin.py
Credentials come from ADMIN_USER_ID / ADMIN_PASSWORD / ADMIN_ZONE in .env.
"""

from pathlib import Path

from sqlalchemy import select

from app.auth import hash_password
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Role, User


def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.user_id == settings.admin_user_id))
        if existing:
            print(f"Admin '{settings.admin_user_id}' already exists.")
            return
        admin = User(
            user_id=settings.admin_user_id,
            password_hash=hash_password(settings.admin_password),
            zone_section=settings.admin_zone,
            role=Role.ADMIN,
        )
        db.add(admin)
        db.commit()
        (Path(settings.main_dir) / admin.user_id).mkdir(parents=True, exist_ok=True)
        print(f"Created admin '{settings.admin_user_id}'.")


if __name__ == "__main__":
    main()
