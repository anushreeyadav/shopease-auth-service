"""API tests for GET /api/auth/me and POST /api/auth/verify-token, through the real application."""

import base64
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.security import create_access_token, hash_password
from app.database.connection import get_db
from app.main import app
from app.models.user_model import User

ME = ("GET", "/api/auth/me")
VERIFY = ("POST", "/api/auth/verify-token")
SECRET = "test-only-jwt-secret-that-is-long-enough"
PASSWORD = "Str0ng!Password"
UNAUTHORIZED = {"detail": "Could not validate credentials"}

both_endpoints = pytest.mark.parametrize("endpoint", [ME, VERIFY], ids=["me", "verify-token"])


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def call(client, endpoint, headers=None):
    method, path = endpoint
    return client.request(method, path, headers=headers or {})


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    user = User(full_name="Asha Rao", email="asha@example.com", password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def token(user):
    return create_access_token(user.id, user.role)


def safe_user(user):
    return {
        "id": user.id,
        "full_name": "Asha Rao",
        "email": "asha@example.com",
        "role": user.role,
        "is_active": True,
    }


# Valid tokens


def test_me_returns_the_safe_profile(client, user, token):
    response = call(client, ME, bearer(token))
    assert response.status_code == 200
    assert response.json() == safe_user(user)


def test_verify_token_returns_validity_and_the_safe_profile(client, user, token):
    response = call(client, VERIFY, bearer(token))
    assert response.status_code == 200
    assert response.json() == {"valid": True, "user": safe_user(user)}


@both_endpoints
def test_token_from_a_real_login_is_accepted(client, user, endpoint):
    login = client.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert call(client, endpoint, bearer(login.json()["access_token"])).status_code == 200


@both_endpoints
def test_authorization_scheme_is_not_case_sensitive(client, token, endpoint):
    assert call(client, endpoint, {"Authorization": f"bearer {token}"}).status_code == 200


@both_endpoints
def test_response_contains_no_sensitive_or_token_details(client, user, token, endpoint):
    text = call(client, endpoint, bearer(token)).text
    assert "password" not in text
    assert user.password_hash not in text
    assert SECRET not in text
    assert token not in text
    for internal in ('"exp"', '"iat"', '"sub"', '"alg"', "HS256", "secret"):
        assert internal not in text


@both_endpoints
def test_role_is_read_from_the_database(client, db, user, token, endpoint):
    user.role = "ADMIN"
    db.commit()
    body = call(client, endpoint, bearer(token)).json()
    assert (body["user"] if endpoint == VERIFY else body)["role"] == "ADMIN"


# Missing tokens


@both_endpoints
def test_missing_token_returns_401(client, endpoint):
    response = call(client, endpoint)
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"


@both_endpoints
@pytest.mark.parametrize("header", ["", "Bearer", "Bearer ", "Basic dXNlcjpwYXNz"])
def test_empty_or_wrong_authorization_header_returns_401(client, user, endpoint, header):
    response = call(client, endpoint, {"Authorization": header})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


@both_endpoints
def test_token_in_the_query_string_is_not_accepted(client, token, endpoint):
    method, path = endpoint
    assert client.request(method, f"{path}?token={token}&access_token={token}").status_code == 401


# Invalid tokens


@both_endpoints
@pytest.mark.parametrize("bad_token", ["not-a-token", "a.b.c", "a.b.c.d", "..."])
def test_malformed_token_returns_401(client, user, endpoint, bad_token):
    response = call(client, endpoint, bearer(bad_token))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


@both_endpoints
def test_token_signed_with_another_secret_returns_401(client, user, endpoint):
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user.id), "role": "USER", "iat": now, "exp": now + timedelta(minutes=5)}
    forged = jwt.encode(claims, "another-secret-of-sufficient-length", algorithm="HS256")
    response = call(client, endpoint, bearer(forged))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


@both_endpoints
def test_token_with_changed_contents_returns_401(client, user, token, endpoint):
    head, body, signature = token.split(".")
    claims = jwt.get_unverified_claims(token)
    tampered = f"{head}.{b64({**claims, 'sub': str(user.id + 1), 'role': 'ADMIN'})}.{signature}"
    assert call(client, endpoint, bearer(tampered)).status_code == 401


@both_endpoints
def test_unsigned_token_returns_401(client, user, endpoint):
    now = int(time.time())
    claims = {"sub": str(user.id), "role": "ADMIN", "iat": now, "exp": now + 300}
    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
    assert call(client, endpoint, bearer(unsigned)).status_code == 401


# Expired tokens


@both_endpoints
def test_expired_token_returns_401(client, user, endpoint):
    expired = create_access_token(user.id, user.role, timedelta(seconds=-1))
    response = call(client, endpoint, bearer(expired))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


@both_endpoints
def test_all_token_failures_get_the_same_response(client, user, endpoint):
    expired = create_access_token(user.id, user.role, timedelta(seconds=-1))
    responses = [
        call(client, endpoint),
        call(client, endpoint, bearer("not-a-token")),
        call(client, endpoint, bearer(expired)),
    ]
    assert all(r.status_code == 401 and r.json() == UNAUTHORIZED for r in responses)


# Inactive and deleted users


@both_endpoints
def test_inactive_user_returns_403(client, db, user, token, endpoint):
    assert call(client, endpoint, bearer(token)).status_code == 200
    user.is_active = False
    db.commit()
    response = call(client, endpoint, bearer(token))
    assert response.status_code == 403
    assert response.json() == {"detail": "Inactive user"}


@both_endpoints
def test_reactivated_user_is_accepted_again(client, db, user, token, endpoint):
    user.is_active = False
    db.commit()
    assert call(client, endpoint, bearer(token)).status_code == 403
    user.is_active = True
    db.commit()
    assert call(client, endpoint, bearer(token)).status_code == 200


@both_endpoints
def test_deleted_user_returns_401(client, db, user, token, endpoint):
    assert call(client, endpoint, bearer(token)).status_code == 200
    db.delete(user)
    db.commit()
    response = call(client, endpoint, bearer(token))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


@both_endpoints
def test_valid_token_for_a_user_that_never_existed_returns_401(client, endpoint):
    assert call(client, endpoint, bearer(create_access_token(999, "USER"))).status_code == 401


# API contract


@pytest.mark.parametrize(("method", "path"), [("POST", ME[1]), ("GET", VERIFY[1])])
def test_wrong_method_returns_405(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 405
    assert "detail" in response.json()


@both_endpoints
def test_openapi_marks_the_endpoint_as_bearer_protected(endpoint):
    method, path = endpoint
    operation = app.openapi()["paths"][path][method.lower()]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "401", "403"} <= set(operation["responses"])
