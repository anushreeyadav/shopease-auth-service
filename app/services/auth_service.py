"""Authentication business logic. This layer knows nothing about HTTP."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.email_utils import normalize_email
from app.core.security import (
    create_access_token,
    hash_password,
    simulate_password_check,
    verify_password,
)
from app.models.user_model import User


class DuplicateEmailError(Exception):
    """The email address already belongs to an account."""


class InvalidCredentialsError(Exception):
    """The email address is unknown, or the password is wrong."""


class InactiveUserError(Exception):
    """The credentials are correct, but the account is deactivated."""


class IncorrectPasswordError(Exception):
    """The current password given for a password change is wrong."""


class PasswordReuseError(Exception):
    """The new password is the same as the current password."""


def get_user_by_email(db: Session, email: str) -> User | None:
    """Find a user by email address, in any letter case."""
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def register_user(db: Session, full_name: str, email: str, password: str) -> User:
    """Create an active account with the default role. The password must already be validated."""
    if get_user_by_email(db, email) is not None:
        raise DuplicateEmailError

    user = User(full_name=full_name, email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Two simultaneous registrations can both pass the check above. The unique index stops one.
        db.rollback()
        raise DuplicateEmailError from exc
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Return the user if the credentials are correct and the account is active."""
    user = get_user_by_email(db, email)
    if user is None:
        simulate_password_check(password)
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    # Checked last, so that only someone with the correct password learns the account's status.
    if not user.is_active:
        raise InactiveUserError
    return user


def login_user(db: Session, email: str, password: str) -> tuple[User, str]:
    """Authenticate the user and return them with a new access token."""
    user = authenticate_user(db, email, password)
    return user, create_access_token(user.id, user.role)


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """Replace the user's password. The new password must already be validated."""
    if not verify_password(current_password, user.password_hash):
        raise IncorrectPasswordError
    # The current password is confirmed above, so comparing the two submitted values is enough.
    if new_password == current_password:
        raise PasswordReuseError

    # The UPDATE also sets updated_at, through the column's onupdate.
    user.password_hash = hash_password(new_password)
    db.commit()
