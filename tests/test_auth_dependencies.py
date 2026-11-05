"""Tests for the authentication dependencies, through a small app with protected routes."""

from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import (
    create_access_token,
    get_current_user,
    get_current_user_id,
    hash_password,
)
from app.database.connection import get_db
from app.models.user_model import User
from app.schemas.auth_schema import UserResponse


@pytest.fixture
def client(db):
    app = FastAPI()

    @app.get("/user-id")
    def read_user_id(user_id: int = Depends(get_current_user_id)):
        return {"user_id": user_id}

    @app.get("/me", response_model=UserResponse)
    def read_me(user: User = Depends(get_current_user)):
        return user

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def user(db):
    user = User(full_name="Test User", email="user@example.com", password_hash=hash_password("Str0ng!Password"))
    db.add(user)
    db.commit()
    return user


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_returns_the_user(client, user):
    response = client.get("/me", headers=bearer(create_access_token(user.id, user.role)))
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_user_id_dependency_returns_the_id_from_the_token(client):
    response = client.get("/user-id", headers=bearer(create_access_token(42, "customer")))
    assert response.status_code == 200
    assert response.json() == {"user_id": 42}


def test_response_does_not_include_the_password_hash(client, user):
    response = client.get("/me", headers=bearer(create_access_token(user.id, user.role)))
    assert "password" not in response.text
    assert user.password_hash not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer not-a-token"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
    ],
)
def test_missing_or_invalid_credentials_return_401(client, user, headers):
    response = client.get("/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {"detail": "Could not validate credentials"}


def test_expired_token_returns_the_same_401(client, user):
    token = create_access_token(user.id, user.role, timedelta(seconds=-1))
    response = client.get("/me", headers=bearer(token))
    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_deleted_user_is_rejected_while_the_token_is_still_valid(client, db, user):
    token = create_access_token(user.id, user.role)
    assert client.get("/me", headers=bearer(token)).status_code == 200
    db.delete(user)
    db.commit()
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_deactivated_user_is_rejected_while_the_token_is_still_valid(client, db, user):
    token = create_access_token(user.id, user.role)
    assert client.get("/me", headers=bearer(token)).status_code == 200
    user.is_active = False
    db.commit()
    response = client.get("/me", headers=bearer(token))
    assert response.status_code == 403
    assert response.json() == {"detail": "Inactive user"}


def test_reactivated_user_is_accepted_again(client, db, user):
    token = create_access_token(user.id, user.role)
    user.is_active = False
    db.commit()
    assert client.get("/me", headers=bearer(token)).status_code == 403
    user.is_active = True
    db.commit()
    assert client.get("/me", headers=bearer(token)).status_code == 200


def test_role_comes_from_the_database_not_the_token(client, db, user):
    token = create_access_token(user.id, "admin")
    response = client.get("/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["role"] == "USER"
