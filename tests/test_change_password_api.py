"""API tests for POST /api/auth/change-password, through the real application."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.security import create_access_token, hash_password, verify_password
from app.database.connection import get_db
from app.main import app
from app.models.user_model import User
from app.services import auth_service

CHANGE_PASSWORD = "/api/auth/change-password"
LOGIN = "/api/auth/login"
EMAIL = "asha@example.com"
CURRENT = "Str0ng!Current"
NEW = "N3w!StrongValue"
SUCCESS = {"message": "Password changed successfully"}
WRONG_CURRENT = {"detail": "Current password is incorrect"}
REUSED = {"detail": "New password must be different from the current password"}
UNAUTHORIZED = {"detail": "Could not validate credentials"}


def change_request(**overrides):
    return {
        "current_password": CURRENT,
        "new_password": NEW,
        "confirm_new_password": NEW,
        **overrides,
    }


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def errors_by_field(response):
    return {error["field"]: error["message"] for error in response.json()["errors"]}


def login_status(client, password):
    return client.post(LOGIN, json={"email": EMAIL, "password": password}).status_code


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    user = User(full_name="Asha Rao", email=EMAIL, password_hash=hash_password(CURRENT))
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def headers(user):
    return bearer(create_access_token(user.id, user.role))


# Successful change


def test_change_password_returns_200_and_a_message(client, headers):
    response = client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    assert response.status_code == 200
    assert response.json() == SUCCESS


def test_old_password_stops_working_and_new_password_works_for_login(client, headers):
    assert login_status(client, CURRENT) == 200
    assert client.post(CHANGE_PASSWORD, json=change_request(), headers=headers).status_code == 200
    assert login_status(client, CURRENT) == 401
    assert login_status(client, NEW) == 200


def test_new_password_is_stored_as_a_new_bcrypt_hash(client, db, user, headers):
    old_hash = user.password_hash
    client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    db.refresh(user)
    assert user.password_hash != old_hash
    assert user.password_hash.startswith("$2b$")
    assert NEW not in user.password_hash
    assert verify_password(NEW, user.password_hash)


def test_change_updates_the_updated_at_timestamp(client, db, user, headers):
    user.updated_at = datetime(2000, 1, 1)
    db.commit()
    client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    db.refresh(user)
    assert user.updated_at > datetime(2000, 1, 1)


def test_change_leaves_other_user_fields_alone(client, db, user, headers):
    before = (user.id, user.full_name, user.email, user.role, user.is_active, user.created_at)
    client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    db.refresh(user)
    assert (user.id, user.full_name, user.email, user.role, user.is_active, user.created_at) == before


def test_change_affects_only_the_authenticated_user(client, db, user, headers):
    other = User(full_name="Other User", email="other@example.com", password_hash=hash_password(CURRENT))
    db.add(other)
    db.commit()
    other_hash = other.password_hash
    client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    db.refresh(other)
    assert other.password_hash == other_hash


def test_change_is_committed(client, db, headers):
    with patch.object(db, "commit", wraps=db.commit) as commit:
        client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    commit.assert_called_once()


def test_password_can_be_changed_twice(client, headers):
    assert client.post(CHANGE_PASSWORD, json=change_request(), headers=headers).status_code == 200
    second = change_request(current_password=NEW, new_password=CURRENT, confirm_new_password=CURRENT)
    assert client.post(CHANGE_PASSWORD, json=second, headers=headers).status_code == 200
    assert login_status(client, CURRENT) == 200
    assert login_status(client, NEW) == 401


def test_success_response_contains_no_password_data(client, db, user, headers):
    old_hash = user.password_hash
    text = client.post(CHANGE_PASSWORD, json=change_request(), headers=headers).text
    db.refresh(user)
    for sensitive in (CURRENT, NEW, old_hash, user.password_hash):
        assert sensitive not in text


# Incorrect current password


@pytest.mark.parametrize(
    "wrong", ["Wr0ng!Password", "str0ng!current", CURRENT + " ", " " + CURRENT, "x", "A" * 200]
)
def test_incorrect_current_password_returns_400(client, user, headers, wrong):
    old_hash = user.password_hash
    response = client.post(CHANGE_PASSWORD, json=change_request(current_password=wrong), headers=headers)
    assert response.status_code == 400
    assert response.json() == WRONG_CURRENT
    assert user.password_hash == old_hash
    assert login_status(client, CURRENT) == 200
    assert login_status(client, NEW) == 401


def test_incorrect_current_password_does_not_reveal_a_reused_password(client, headers):
    reused = change_request(current_password="Wr0ng!Password", new_password=CURRENT, confirm_new_password=CURRENT)
    response = client.post(CHANGE_PASSWORD, json=reused, headers=headers)
    assert response.json() == WRONG_CURRENT


def test_current_password_is_checked_before_comparing_it_with_the_new_one(client, headers):
    wrong = "Wr0ng!Password"
    body = change_request(current_password=wrong, new_password=wrong, confirm_new_password=wrong)
    response = client.post(CHANGE_PASSWORD, json=body, headers=headers)
    assert response.status_code == 400
    assert response.json() == WRONG_CURRENT


# Weak new password


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Ab1!xyz", "at least 8 characters"),
        ("n3w!strongvalue", "uppercase"),
        ("N3W!STRONGVALUE", "lowercase"),
        ("New!StrongValue", "number"),
        ("N3wStrongValue", "special character"),
        ("A1!" + "b" * 70, "at most 72 bytes"),
    ],
)
def test_weak_new_password_returns_422(client, user, headers, password, expected):
    old_hash = user.password_hash
    body = change_request(new_password=password, confirm_new_password=password)
    response = client.post(CHANGE_PASSWORD, json=body, headers=headers)
    assert response.status_code == 422
    assert expected in errors_by_field(response)["new_password"]
    assert user.password_hash == old_hash


# Mismatched confirmation


def test_mismatched_confirmation_returns_422(client, user, headers):
    old_hash = user.password_hash
    body = change_request(confirm_new_password="Different1!Password")
    response = client.post(CHANGE_PASSWORD, json=body, headers=headers)
    assert response.status_code == 422
    assert errors_by_field(response) == {"confirm_new_password": "Passwords do not match"}
    assert user.password_hash == old_hash


# Reusing the current password


def test_reusing_the_current_password_returns_400(client, user, headers):
    old_hash = user.password_hash
    body = change_request(new_password=CURRENT, confirm_new_password=CURRENT)
    response = client.post(CHANGE_PASSWORD, json=body, headers=headers)
    assert response.status_code == 400
    assert response.json() == REUSED
    assert user.password_hash == old_hash
    assert login_status(client, CURRENT) == 200


def test_rejected_change_does_not_hash_or_commit(client, db, headers):
    body = change_request(new_password=CURRENT, confirm_new_password=CURRENT)
    with (
        patch.object(auth_service, "hash_password") as hashing,
        patch.object(db, "commit") as commit,
    ):
        client.post(CHANGE_PASSWORD, json=body, headers=headers)
    hashing.assert_not_called()
    commit.assert_not_called()


# Authentication


def test_request_without_a_token_returns_401(client, user):
    response = client.post(CHANGE_PASSWORD, json=change_request())
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert login_status(client, CURRENT) == 200


def test_request_with_an_invalid_token_returns_401(client, user):
    response = client.post(CHANGE_PASSWORD, json=change_request(), headers=bearer("not-a-token"))
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_request_with_an_expired_token_returns_401(client, user):
    expired = create_access_token(user.id, user.role, timedelta(seconds=-1))
    response = client.post(CHANGE_PASSWORD, json=change_request(), headers=bearer(expired))
    assert response.status_code == 401
    assert login_status(client, CURRENT) == 200


def test_inactive_user_returns_403_and_keeps_the_password(client, db, user, headers):
    old_hash = user.password_hash
    user.is_active = False
    db.commit()
    response = client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Inactive user"}
    assert user.password_hash == old_hash


def test_deleted_user_returns_401(client, db, user, headers):
    db.delete(user)
    db.commit()
    assert client.post(CHANGE_PASSWORD, json=change_request(), headers=headers).status_code == 401


# Request validation


@pytest.mark.parametrize("field", ["current_password", "new_password", "confirm_new_password"])
def test_every_field_is_required(client, headers, field):
    body = change_request()
    del body[field]
    response = client.post(CHANGE_PASSWORD, json=body, headers=headers)
    assert response.status_code == 422
    assert field in errors_by_field(response)


def test_empty_current_password_returns_422(client, headers):
    response = client.post(CHANGE_PASSWORD, json=change_request(current_password=""), headers=headers)
    assert response.status_code == 422
    assert "current_password" in errors_by_field(response)


@pytest.mark.parametrize(
    "overrides",
    [
        {"new_password": "weakSECRETvalue", "confirm_new_password": "weakSECRETvalue"},
        {"confirm_new_password": "Different1!SECRETvalue"},
        {"current_password": 12345},
    ],
)
def test_validation_errors_do_not_echo_submitted_values(client, headers, overrides):
    response = client.post(CHANGE_PASSWORD, json=change_request(**overrides), headers=headers)
    assert response.status_code == 422
    assert "SECRET" not in response.text
    assert "12345" not in response.text
    assert "input" not in response.text


# Failures and the API contract


def test_database_failure_returns_a_generic_503(client, db, headers):
    failure = OperationalError("UPDATE secret_statement", {}, Exception("host and password details"))
    with patch.object(db, "commit", side_effect=failure):
        response = client.post(CHANGE_PASSWORD, json=change_request(), headers=headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}


def test_get_method_returns_405(client):
    assert client.get(CHANGE_PASSWORD).status_code == 405


def test_openapi_describes_the_endpoint():
    operation = app.openapi()["paths"][CHANGE_PASSWORD]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "400", "401", "403", "422"} <= set(operation["responses"])
