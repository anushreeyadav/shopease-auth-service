"""Tests for the assembled application: routes, documentation, status codes, and session cleanup.

Unlike the other API tests, the session tests use the real get_db dependency.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token, hash_password
from app.database import connection
from app.database.connection import get_db
from app.main import app
from app.models.user_model import User
from app.services import auth_service

PASSWORD = "Str0ng!Password"
NEW_PASSWORD = "N3w!StrongValue"
REGISTER_BODY = {
    "full_name": "Asha Rao",
    "email": "new@example.com",
    "password": PASSWORD,
    "confirm_password": PASSWORD,
}
LOGIN_BODY = {"email": "asha@example.com", "password": PASSWORD}
CHANGE_BODY = {
    "current_password": PASSWORD,
    "new_password": NEW_PASSWORD,
    "confirm_new_password": NEW_PASSWORD,
}
AUTH_ENDPOINTS = {
    ("post", "/api/auth/register"),
    ("post", "/api/auth/login"),
    ("get", "/api/auth/me"),
    ("post", "/api/auth/verify-token"),
    ("post", "/api/auth/change-password"),
}
PROTECTED_ENDPOINTS = {
    ("get", "/api/auth/me"),
    ("post", "/api/auth/verify-token"),
    ("post", "/api/auth/change-password"),
}


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    user = User(full_name="Asha Rao", email="asha@example.com", password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# Routes and documentation


def test_all_authentication_endpoints_are_registered():
    paths = app.openapi()["paths"]
    registered = {
        (method, path) for path, operations in paths.items() if path.startswith("/api/auth")
        for method in operations
    }
    assert registered == AUTH_ENDPOINTS


def test_api_title_description_and_version_are_configured():
    info = app.openapi()["info"]
    assert info["title"] == "ShopEase Auth Service"
    assert info["version"] == "0.1.0"
    assert "Authentication microservice" in info["description"]


def test_health_endpoint_needs_no_authentication_or_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ShopEase Auth Service", "version": "0.1.0"}


def test_swagger_ui_is_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_openapi_uses_http_bearer_authentication():
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {"type": "http", "scheme": "bearer"}
    for method, path in PROTECTED_ENDPOINTS:
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]


@pytest.mark.parametrize("endpoint", sorted(AUTH_ENDPOINTS - PROTECTED_ENDPOINTS))
def test_public_endpoints_do_not_ask_for_a_token(endpoint):
    method, path = endpoint
    assert "security" not in app.openapi()["paths"][path][method]


def test_openapi_exposes_no_password_hash_or_secret():
    schema = str(app.openapi())
    assert "password_hash" not in schema
    assert "jwt_secret" not in schema.lower()


# Status codes


def test_status_200_for_login_and_protected_requests(client, user, headers):
    assert client.post("/api/auth/login", json=LOGIN_BODY).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/verify-token", headers=headers).status_code == 200
    assert client.post("/api/auth/change-password", json=CHANGE_BODY, headers=headers).status_code == 200


def test_status_201_for_registration(client):
    assert client.post("/api/auth/register", json=REGISTER_BODY).status_code == 201


def test_status_400_for_a_failed_password_change(client, headers):
    body = {**CHANGE_BODY, "current_password": "Wr0ng!Password"}
    assert client.post("/api/auth/change-password", json=body, headers=headers).status_code == 400


def test_status_401_for_missing_authentication(client):
    assert client.get("/api/auth/me").status_code == 401


def test_status_404_for_an_unknown_path_has_the_standard_format(client):
    response = client.get("/api/auth/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_status_409_for_a_duplicate_email(client, user):
    body = {**REGISTER_BODY, "email": "asha@example.com"}
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_status_422_for_invalid_data(client):
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 422
    assert response.json()["detail"] == "Validation failed"


def test_status_500_hides_the_internal_error(client, user, headers):
    with patch.object(auth_service, "change_password", side_effect=RuntimeError("internal details")):
        response = client.post("/api/auth/change-password", json=CHANGE_BODY, headers=headers)
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


# Sensitive data


def test_no_response_contains_password_data(client, db, user, headers):
    responses = [
        client.post("/api/auth/register", json=REGISTER_BODY),
        client.post("/api/auth/login", json=LOGIN_BODY),
        client.get("/api/auth/me", headers=headers),
        client.post("/api/auth/verify-token", headers=headers),
        client.post("/api/auth/change-password", json=CHANGE_BODY, headers=headers),
    ]
    hashes = [hash_ for (hash_,) in db.query(User.password_hash).all()]
    for response in responses:
        assert response.status_code < 300
        assert "password_hash" not in response.text
        for sensitive in (PASSWORD, NEW_PASSWORD, *hashes):
            assert sensitive not in response.text


# Session cleanup, using the real get_db dependency


@pytest.fixture
def sessions(db, monkeypatch):
    """Replace SessionLocal with one that records how many sessions were opened and closed."""
    counts = {"opened": 0, "closed": 0}

    class CountingSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            counts["opened"] += 1

        def close(self):
            counts["closed"] += 1
            super().close()

    factory = sessionmaker(bind=db.get_bind(), class_=CountingSession, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(connection, "SessionLocal", factory)
    return counts


@pytest.mark.parametrize(
    ("method", "path", "body", "use_token", "expected"),
    [
        ("post", "/api/auth/register", REGISTER_BODY, False, 201),
        ("post", "/api/auth/login", LOGIN_BODY, False, 200),
        ("post", "/api/auth/login", {**LOGIN_BODY, "password": "Wr0ng!Password"}, False, 401),
        ("post", "/api/auth/login", {}, False, 422),
        ("get", "/api/auth/me", None, True, 200),
        ("post", "/api/auth/change-password", CHANGE_BODY, True, 200),
        ("post", "/api/auth/change-password", {**CHANGE_BODY, "current_password": "Wr0ng!Password"}, True, 400),
        ("get", "/health/db", None, False, 200),
    ],
)
def test_every_session_is_closed_after_the_request(sessions, user, headers, method, path, body, use_token, expected):
    client = TestClient(app)
    response = client.request(method, path, json=body, headers=headers if use_token else {})
    assert response.status_code == expected
    assert sessions == {"opened": 1, "closed": 1}


def test_missing_token_is_rejected_without_opening_a_session(sessions):
    assert TestClient(app).get("/api/auth/me").status_code == 401
    assert sessions == {"opened": 0, "closed": 0}


def test_session_is_closed_after_an_unexpected_error(sessions, user):
    client = TestClient(app, raise_server_exceptions=False)
    with patch.object(auth_service, "login_user", side_effect=RuntimeError("internal details")):
        response = client.post("/api/auth/login", json=LOGIN_BODY)
    assert response.status_code == 500
    assert sessions == {"opened": 1, "closed": 1}


def test_password_change_survives_the_end_of_the_request_session(sessions, db, user, headers):
    client = TestClient(app)
    assert client.post("/api/auth/change-password", json=CHANGE_BODY, headers=headers).status_code == 200
    assert client.post("/api/auth/login", json=LOGIN_BODY).status_code == 401
    new_login = {**LOGIN_BODY, "password": NEW_PASSWORD}
    assert client.post("/api/auth/login", json=new_login).status_code == 200
