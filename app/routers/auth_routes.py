"""HTTP layer for authentication: request handling only, no business logic."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.user_model import User
from app.schemas.auth_schema import (
    ChangePasswordRequest,
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    TokenVerificationResponse,
    UserResponse,
    ValidationErrorResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

PROTECTED_ROUTE_ERRORS = {
    401: {"model": ErrorResponse, "description": "Token is missing or invalid, or the user no longer exists"},
    403: {"model": ErrorResponse, "description": "Inactive user"},
}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"model": ValidationErrorResponse, "description": "Invalid request data"},
    },
)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_user(db, request.full_name, request.email, request.password)
    except auth_service.DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    return {"message": "User registered successfully", "user": user}


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in and get an access token",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid email or password"},
        403: {"model": ErrorResponse, "description": "Inactive user"},
        422: {"model": ValidationErrorResponse, "description": "Invalid request data"},
    },
)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, access_token = auth_service.login_user(db, request.email, request.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except auth_service.InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user") from exc
    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current user",
    responses=PROTECTED_ROUTE_ERRORS,
)
def read_current_user(user: User = Depends(get_current_user)):
    return user


@router.post(
    "/verify-token",
    response_model=TokenVerificationResponse,
    summary="Verify an access token",
    responses=PROTECTED_ROUTE_ERRORS,
)
def verify_token(user: User = Depends(get_current_user)):
    return {"valid": True, "user": user}


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change the current user's password",
    responses={
        400: {"model": ErrorResponse, "description": "Current password is wrong, or the new password is the same"},
        **PROTECTED_ROUTE_ERRORS,
        422: {"model": ValidationErrorResponse, "description": "Invalid request data"},
    },
)
def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        auth_service.change_password(db, user, request.current_password, request.new_password)
    except auth_service.IncorrectPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect") from exc
    except auth_service.PasswordReuseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        ) from exc
    return {"message": "Password changed successfully"}
