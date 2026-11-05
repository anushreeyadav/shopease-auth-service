"""Password hashing, JWT handling, and the authentication dependencies for routes.

All cryptographic code lives here, not in routers or services.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import get_db
from app.models.user_model import User

MIN_PASSWORD_LENGTH = 8
# bcrypt ignores everything after 72 bytes, so longer passwords are rejected, not truncated.
MAX_PASSWORD_BYTES = 72

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# auto_error=False: a missing token gets this service's own 401 response.
bearer_scheme = HTTPBearer(auto_error=False)


class InvalidTokenError(Exception):
    """The token is expired, malformed, wrongly signed, or missing a required claim."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    role: str


def _password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def validate_password_strength(password: str) -> None:
    """Raise ValueError listing every unmet rule. The password is never part of the message."""
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"be at least {MIN_PASSWORD_LENGTH} characters long")
    if _password_too_long(password):
        problems.append(f"be at most {MAX_PASSWORD_BYTES} bytes long")
    if not any(char.isupper() for char in password):
        problems.append("contain an uppercase letter")
    if not any(char.islower() for char in password):
        problems.append("contain a lowercase letter")
    if not any(char.isdigit() for char in password):
        problems.append("contain a number")
    if not any(not char.isalnum() and not char.isspace() for char in password):
        problems.append("contain a special character")
    if "\x00" in password:  # bcrypt cannot hash a null character
        problems.append("not contain a null character")
    if problems:
        raise ValueError("Password must " + ", ".join(problems))


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash. Strength rules are checked separately, by the request schemas."""
    if _password_too_long(password):
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long")
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True only if the password matches. A malformed hash counts as no match."""
    # Without this check, a longer password could match on its first 72 bytes alone.
    if _password_too_long(password):
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


@lru_cache
def _dummy_password_hash() -> str:
    return pwd_context.hash(secrets.token_urlsafe(32))


def simulate_password_check(password: str) -> None:
    """Spend the time of a real check, so that response times do not reveal unknown emails."""
    verify_password(password, _dummy_password_hash())


def create_access_token(user_id: int, role: str, expires_delta: timedelta | None = None) -> str:
    """Return a signed JWT. The lifetime defaults to ACCESS_TOKEN_EXPIRE_MINUTES."""
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    issued_at = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "role": role, "iat": issued_at, "exp": issued_at + expires_delta}
    return jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """Verify a token and return its claims, or raise InvalidTokenError."""
    settings = get_settings()
    try:
        # Only the configured algorithm is accepted, whatever the token's own header says.
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require_sub": True, "require_exp": True, "require_iat": True},
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    subject, role = claims["sub"], claims.get("role")
    if not (subject.isascii() and subject.isdecimal()) or not isinstance(role, str) or not role:
        raise InvalidTokenError("Invalid token claims")
    return TokenPayload(user_id=int(subject), role=role)


def _credentials_error() -> HTTPException:
    # One response for every failure, so that callers cannot learn why a token was rejected.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    """Dependency: read the bearer token from the request and validate it."""
    if credentials is None:
        raise _credentials_error()
    try:
        return decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise _credentials_error() from exc


def get_current_user_id(payload: TokenPayload = Depends(get_token_payload)) -> int:
    """Dependency: return the authenticated user's ID from the token, with no database query."""
    return payload.user_id


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: return the authenticated user, loaded from the database on every request.

    A deleted or deactivated user is rejected at once, even if their token has not expired.
    Use user.role from this object for permission checks: the token's role may be out of date.
    """
    user = db.get(User, user_id)
    if user is None:
        raise _credentials_error()
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user
