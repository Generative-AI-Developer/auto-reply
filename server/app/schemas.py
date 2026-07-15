from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import Status


# --- Auth ---------------------------------------------------------------------
class LoginRequest(BaseModel):
    user_id: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


# --- Users --------------------------------------------------------------------
class UserCreate(BaseModel):
    user_id: str = Field(min_length=1)
    zone_section: str = ""
    password: str = Field(min_length=1)
    role: str = "user"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    zone_section: str
    role: str
    created_at: datetime


# --- Requests -----------------------------------------------------------------
class RequestCreate(BaseModel):
    numbers: list[str] = Field(default_factory=list, description="mobile / NIC / any other numbers")
    duration_days: int | None = None
    case_officer: str = ""
    justification: str = ""
    request_date: date | None = None


class ResponseFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    matched_value: str
    matched_date: date | None
    received_at: datetime


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: str
    owner_user_id: str
    numbers: list[str]
    duration_days: int | None
    case_officer: str
    justification: str
    request_date: date | None
    status: str
    created_at: datetime
    files: list[ResponseFileOut] = []


class StatusUpdate(BaseModel):
    status: str

    def is_valid_manual(self) -> bool:
        return self.status in Status.MANUAL


class ImportResult(BaseModel):
    created: int
    failed: int
    errors: list[str] = []
