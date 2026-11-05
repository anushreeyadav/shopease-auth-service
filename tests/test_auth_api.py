"""API tests for registration and login, through the real application."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.exc import OperationalError

from app.core.security import decode_access_token, verify_password
from app.database.connection import get_db
from app.main import app
from app.models.user_model import User
from app.services import auth_service

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
PASSWORD = "Str0ng!Password"


def registration(**overrides):
    return {
        "full_name": "Asha Rao",
        "email": "asha@example.com",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        **overrides,
    }


def errors_by_field(response):
    return {error["field"]: error["message"] for error in response.json()["errors"]}


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def registered(client):
    response = client.post(REGISTER, json=registration())
    assert response.status_code == 201
    return response.json()["user"]


# Registration: success


def test_register_returns_201_and_the_user(client):
    response = client.post(REGISTER, json=registration())
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "User registered successfully"
    assert set(body["user"]) == {"id", "full_name", "email", "role", "is_active"}
    assert body["user"]["id"] > 0
    assert body["user"]["full_name"] == "Asha Rao"
    assert body["user"]["email"] == "asha@example.com"


def test_register_assigns_the_default_role_and_active_status(client):
    user = client.post(REGISTER, json=registration()).json()["user"]
    assert user["role"] == "USER"
    assert user["is_active"] is True


def test_register_saves_the_user(client, db):
    client.post(REGISTER, json=registration())
    user = db.query(User).one()
    assert user.full_name == "Asha Rao"
    assert user.email == "asha@example.com"


def test_register_stores_a_hash_and_not_the_password(client, db):
    client.post(REGISTER, json=registration())
    stored = db.query(User).one().password_hash
    assert stored.startswith("$2b$")
    assert PASSWORD not in stored
    assert verify_password(PASSWORD, stored)


def test_register_response_contains_no_password_data(client, db):
    response = client.post(REGISTER, json=registration())
    assert "password" not in response.text
    assert PASSWORD not in response.text
    assert db.query(User).one().password_hash not in response.text


def test_register_normalizes_the_email(client):
    response = client.post(REGISTER, json=registration(email="  Asha.RAO@Example.COM "))
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "asha.rao@example.com"


def test_register_trims_the_full_name(client):
    response = client.post(REGISTER, json=registration(full_name="  Asha Rao  "))
    assert response.json()["user"]["full_name"] == "Asha Rao"


@pytest.mark.parametrize("field", ["role", "is_active", "id", "password_hash"])
def test_register_ignores_fields_the_client_must_not_set(client, db, field):
    values = {"role": "ADMIN", "is_active": False, "id": 999, "password_hash": "x"}
    response = client.post(REGISTER, json=registration(**{field: values[field]}))
    assert response.status_code == 201
    user = db.query(User).one()
    assert user.role == "USER"
    assert user.is_active is True
    assert user.id != 999
    assert user.password_hash != "x"


# Registration: validation


@pytest.mark.parametrize("field", ["full_name", "email", "password", "confirm_password"])
def test_register_requires_every_field(client, db, field):
    body = registration()
    del body[field]
    response = client.post(REGISTER, json=body)
    assert response.status_code == 422
    assert field in errors_by_field(response)
    assert db.query(User).count() == 0


@pytest.mark.parametrize("name", ["", "   ", "x" * 256])
def test_register_rejects_an_invalid_full_name(client, name):
    response = client.post(REGISTER, json=registration(full_name=name))
    assert response.status_code == 422
    assert "full_name" in errors_by_field(response)


@pytest.mark.parametrize("email", ["", "not-an-email", "a@", "@example.com", "a b@example.com", "a@b", 123])
def test_register_rejects_an_invalid_email(client, email):
    response = client.post(REGISTER, json=registration(email=email))
    assert response.status_code == 422
    assert "email" in errors_by_field(response)


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Ab1!xyz", "at least 8 characters"),
        ("str0ng!password", "uppercase"),
        ("STR0NG!PASSWORD", "lowercase"),
        ("Strong!Password", "number"),
        ("Str0ngPassword", "special character"),
        ("A1!" + "b" * 70, "at most 72 bytes"),
    ],
)
def test_register_rejects_a_weak_password(client, db, password, expected):
    response = client.post(REGISTER, json=registration(password=password, confirm_password=password))
    assert response.status_code == 422
    assert expected in errors_by_field(response)["password"]
    assert db.query(User).count() == 0


def test_register_rejects_mismatched_passwords(client, db):
    response = client.post(REGISTER, json=registration(confirm_password="Different1!Password"))
    assert response.status_code == 422
    assert errors_by_field(response) == {"confirm_password": "Passwords do not match"}
    assert db.query(User).count() == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "weakSECRETvalue", "confirm_password": "weakSECRETvalue"},
        {"confirm_password": "Different1!SECRETvalue"},
        {"password": 12345},
    ],
)
def test_validation_errors_do_not_echo_submitted_values(client, overrides):
    response = client.post(REGISTER, json=registration(**overrides))
    assert response.status_code == 422
    assert "SECRET" not in response.text
    assert "12345" not in response.text
    assert "input" not in response.text


def test_validation_error_format(client):
    response = client.post(REGISTER, json=registration(email="bad"))
    body = response.json()
    assert set(body) == {"detail", "errors"}
    assert body["detail"] == "Validation failed"
    assert set(body["errors"][0]) == {"field", "message"}


def test_invalid_json_returns_the_validation_format(client):
    response = client.post(REGISTER, content="{not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Validation failed"
    assert response.json()["errors"][0]["field"] == "body"


@pytest.mark.parametrize("field", ["full_name", "email", "password", "confirm_password"])
def test_invalid_unicode_is_rejected_cleanly(client, field):
    body = json.dumps(registration()).replace(json.dumps(registration()[field]), '"bad\\ud800value"', 1)
    response = client.post(REGISTER, content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422


# Registration: duplicates


def test_register_rejects_a_duplicate_email(client, db, registered):
    response = client.post(REGISTER, json=registration(full_name="Someone Else"))
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert db.query(User).count() == 1


@pytest.mark.parametrize("email", ["ASHA@EXAMPLE.COM", "Asha@Example.com", "  asha@example.com  "])
def test_register_rejects_a_duplicate_in_another_form(client, db, registered, email):
    assert client.post(REGISTER, json=registration(email=email)).status_code == 409
    assert db.query(User).count() == 1


def test_duplicate_is_detected_before_hashing_the_password(client, registered):
    with patch.object(auth_service, "hash_password") as hashing:
        assert client.post(REGISTER, json=registration()).status_code == 409
    hashing.assert_not_called()


def test_service_lookup_normalizes_the_email_itself(db, client, registered):
    user = auth_service.get_user_by_email(db, "  ASHA@Example.COM ")
    assert user is not None
    assert user.id == registered["id"]


def test_simultaneous_duplicate_is_stopped_by_the_unique_index(client, db, registered):
    # Both requests pass the first check, as in a race. The database must then reject the second.
    with patch.object(auth_service, "get_user_by_email", return_value=None):
        response = client.post(REGISTER, json=registration())
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert db.query(User).count() == 1


# Login: success


def test_login_returns_a_token_and_the_user(client, registered):
    response = client.post(LOGIN, json={"email": "asha@example.com", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"message", "access_token", "token_type", "user"}
    assert body["message"] == "Login successful"
    assert body["token_type"] == "bearer"
    assert body["user"] == registered


def test_login_token_is_valid_and_identifies_the_user(client, registered):
    token = client.post(LOGIN, json={"email": "asha@example.com", "password": PASSWORD}).json()["access_token"]
    payload = decode_access_token(token)
    assert payload.user_id == registered["id"]
    assert payload.role == "USER"
    assert set(jwt.get_unverified_claims(token)) == {"sub", "role", "iat", "exp"}


def test_login_response_contains_no_password_data(client, db, registered):
    response = client.post(LOGIN, json={"email": "asha@example.com", "password": PASSWORD})
    assert "password" not in response.text
    assert PASSWORD not in response.text
    assert db.query(User).one().password_hash not in response.text


@pytest.mark.parametrize("email", ["ASHA@EXAMPLE.COM", "Asha@Example.Com", "  asha@example.com "])
def test_login_normalizes_the_email(client, registered, email):
    assert client.post(LOGIN, json={"email": email, "password": PASSWORD}).status_code == 200


# Login: rejected


@pytest.mark.parametrize(
    "password", ["Wr0ng!Password", "str0ng!password", PASSWORD + " ", " " + PASSWORD, "x", "A" * 200]
)
def test_login_rejects_an_incorrect_password(client, registered, password):
    response = client.post(LOGIN, json={"email": "asha@example.com", "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_unknown_email_and_wrong_password_get_the_same_response(client, registered):
    wrong_password = client.post(LOGIN, json={"email": "asha@example.com", "password": "Wr0ng!Password"})
    unknown_email = client.post(LOGIN, json={"email": "nobody@example.com", "password": "Wr0ng!Password"})
    assert unknown_email.status_code == wrong_password.status_code == 401
    assert unknown_email.json() == wrong_password.json()
    assert unknown_email.headers["WWW-Authenticate"] == wrong_password.headers["WWW-Authenticate"]


def test_login_with_an_unknown_email_still_performs_a_password_check(client):
    with patch.object(auth_service, "simulate_password_check") as simulated:
        client.post(LOGIN, json={"email": "nobody@example.com", "password": "Wr0ng!Password"})
    simulated.assert_called_once_with("Wr0ng!Password")


def test_inactive_user_with_the_correct_password_gets_403_and_no_token(client, db, registered):
    db.query(User).one().is_active = False
    db.commit()
    response = client.post(LOGIN, json={"email": "asha@example.com", "password": PASSWORD})
    assert response.status_code == 403
    assert response.json() == {"detail": "Inactive user"}
    assert "access_token" not in response.text


def test_inactive_status_is_hidden_from_a_wrong_password(client, db, registered):
    db.query(User).one().is_active = False
    db.commit()
    response = client.post(LOGIN, json={"email": "asha@example.com", "password": "Wr0ng!Password"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"email": "asha@example.com"},
        {"password": PASSWORD},
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "asha@example.com", "password": ""},
    ],
)
def test_login_validates_the_request(client, body):
    response = client.post(LOGIN, json=body)
    assert response.status_code == 422
    assert response.json()["detail"] == "Validation failed"
    assert PASSWORD not in response.text


def test_login_accepts_any_password_format_without_revealing_the_rules(client, registered):
    response = client.post(LOGIN, json={"email": "asha@example.com", "password": "weak"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


# Unexpected failures


def test_database_failure_returns_a_generic_503(client):
    failure = OperationalError("SELECT secret_statement", {}, Exception("host and password details"))
    with patch.object(auth_service, "get_user_by_email", side_effect=failure):
        response = client.post(LOGIN, json={"email": "asha@example.com", "password": PASSWORD})
    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}


def test_unexpected_failure_returns_a_generic_500(db):
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch.object(auth_service, "get_user_by_email", side_effect=RuntimeError("internal details")):
            response = client.post(LOGIN, json={"email": "asha@example.com", "password": PASSWORD})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
