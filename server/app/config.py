from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./autoreply.db"

    # Auth
    jwt_secret: str = "change-me"
    jwt_expire_min: int = 720
    jwt_algorithm: str = "HS256"

    # Folders
    # main_dir is BOTH the watched inbox (watchdog watches its top level only,
    # non-recursive) AND the root of the permanent per-user/per-request tree:
    #   main_dir/<user_id>/<request_id>/   <- created eagerly, holds matched files
    # A raw file dropped directly in main_dir/ gets matched and moved down into
    # the right <user_id>/<request_id>/ folder(s); nested folders are never
    # rescanned since the observer isn't recursive.
    main_dir: Path = Path("./main")
    unmatched_dir: Path = Path("./unmatched")

    # Networking
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Bootstrap admin (seed_admin.py)
    admin_user_id: str = "admin"
    admin_password: str = "admin123"
    admin_zone: str = "HQ"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        for d in (self.main_dir, self.unmatched_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
