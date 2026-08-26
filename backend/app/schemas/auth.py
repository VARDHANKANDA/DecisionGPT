from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = r"[^@\s]+@[^@\s]+\.[^@\s]+"


class _EmailMixin(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        import re

        v = v.strip().lower()
        if not re.fullmatch(_EMAIL_RE, v):
            raise ValueError("Invalid email address.")
        return v


class RegisterRequest(_EmailMixin):
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: str = "sme"  # "sme" | "admin"


class LoginRequest(_EmailMixin):
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
