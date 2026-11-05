"""Pydantic request and response schemas."""

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from app.core.email_utils import normalize_email
from app.core.security import validate_password_strength


def _normalize_email_input(value: Any) -> Any:
    return normalize_email(value) if isinstance(value, str) else value


NormalizedEmail = Annotated[EmailStr, BeforeValidator(_normalize_email_input)]


class RegisterRequest(BaseModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    email: NormalizedEmail
    # repr=False keeps passwords out of anything that prints or logs the request object.
    password: str = Field(repr=False)
    confirm_password: str = Field(repr=False)

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        validate_password_strength(value)
        return value

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        # "password" is absent if it already failed; that error is reported on its own.
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class LoginRequest(BaseModel):
    email: NormalizedEmail
    # Strength rules apply only when a password is set. Here, a wrong password is simply a failed login.
    password: str = Field(min_length=1, repr=False)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, repr=False)
    new_password: str = Field(repr=False)
    confirm_new_password: str = Field(repr=False)

    @field_validator("new_password")
    @classmethod
    def new_password_is_strong(cls, value: str) -> str:
        validate_password_strength(value)
        return value

    @field_validator("confirm_new_password")
    @classmethod
    def new_passwords_match(cls, value: str, info: ValidationInfo) -> str:
        # "new_password" is absent if it already failed; that error is reported on its own.
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return value


class UserResponse(BaseModel):
    # The user fields an API may return. password_hash is deliberately not one of them.
    # A comment, not a docstring: FastAPI publishes docstrings in the OpenAPI schema.
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str
    is_active: bool


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
    user: UserResponse


class TokenVerificationResponse(BaseModel):
    valid: bool
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    detail: str
    errors: list[FieldError]


class RootResponse(BaseModel):
    service: str
    version: str
    docs_url: str | None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
