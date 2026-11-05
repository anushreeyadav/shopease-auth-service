"""Unit tests for JWT generation, decoding, and expiration."""

import base64
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import InvalidTokenError, create_access_token, decode_access_token

SECRET = "test-only-jwt-secret-that-is-long-enough"


def sign(claims, secret=SECRET, algorithm="HS256"):
    return jwt.encode(claims, secret, algorithm=algorithm)


def valid_claims(**overrides):
    now = datetime.now(timezone.utc)
    return {"sub": "1", "role": "customer", "iat": now, "exp": now + timedelta(minutes=5), **overrides}


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def test_token_has_the_required_claims():
    claims = jwt.get_unverified_claims(create_access_token(42, "admin"))
    assert set(claims) == {"sub", "role", "iat", "exp"}
    assert claims["sub"] == "42"
    assert isinstance(claims["sub"], str)
    assert claims["role"] == "admin"


def test_token_contains_no_sensitive_data():
    token = create_access_token(42, "customer")
    assert SECRET not in token
    assert not set(jwt.get_unverified_claims(token)) & {"email", "password", "password_hash"}


def test_token_uses_the_configured_algorithm(monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_algorithm", "HS512")
    token = create_access_token(1, "customer")
    assert jwt.get_unverified_header(token)["alg"] == "HS512"
    assert decode_access_token(token).user_id == 1


def test_token_uses_the_configured_secret(monkeypatch):
    token = create_access_token(1, "customer")
    monkeypatch.setattr(get_settings().jwt_secret_key, "_secret_value", "another-secret-of-sufficient-length")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_expiry_defaults_to_the_configured_minutes(monkeypatch):
    monkeypatch.setattr(get_settings(), "access_token_expire_minutes", 7)
    claims = jwt.get_unverified_claims(create_access_token(1, "customer"))
    assert claims["exp"] - claims["iat"] == 7 * 60


def test_issued_at_is_the_current_time():
    claims = jwt.get_unverified_claims(create_access_token(1, "customer"))
    assert abs(claims["iat"] - time.time()) < 5


def test_expiry_can_be_set_for_one_token():
    claims = jwt.get_unverified_claims(create_access_token(1, "customer", timedelta(minutes=2)))
    assert claims["exp"] - claims["iat"] == 120


def test_decode_returns_the_user_id_and_role():
    payload = decode_access_token(create_access_token(42, "admin"))
    assert payload.user_id == 42
    assert payload.role == "admin"


def test_expired_token_is_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token(create_access_token(1, "customer", timedelta(seconds=-1)))


def test_token_stops_working_when_its_lifetime_ends():
    token = create_access_token(1, "customer", timedelta(seconds=1))
    assert decode_access_token(token).user_id == 1
    time.sleep(2.1)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


@pytest.mark.parametrize(
    "token",
    ["", "not-a-token", "a.b", "a.b.c", "a.b.c.d", "é.é.é", "Bearer abc", "...", "eyJhbGciOiJIUzI1NiJ9.e30."],
)
def test_malformed_token_is_rejected(token):
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_token_signed_with_another_secret_is_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token(sign(valid_claims(), secret="another-secret-of-sufficient-length"))


def test_token_with_a_changed_signature_is_rejected():
    head, body, signature = create_access_token(1, "customer").split(".")
    replacement = "A" if signature[0] != "A" else "B"
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{head}.{body}.{replacement}{signature[1:]}")


def test_token_with_a_changed_role_is_rejected():
    head, _, signature = create_access_token(1, "customer").split(".")
    claims = jwt.get_unverified_claims(create_access_token(1, "customer"))
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{head}.{b64({**claims, 'role': 'admin'})}.{signature}")


def test_unsigned_alg_none_token_is_rejected():
    now = int(time.time())
    claims = {"sub": "1", "role": "admin", "iat": now, "exp": now + 300}
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}.")


def test_token_with_a_different_algorithm_is_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token(sign(valid_claims(), algorithm="HS512"))


@pytest.mark.parametrize("missing", ["sub", "role", "iat", "exp"])
def test_correctly_signed_token_missing_a_claim_is_rejected(missing):
    claims = valid_claims()
    del claims[missing]
    with pytest.raises(InvalidTokenError):
        decode_access_token(sign(claims))


@pytest.mark.parametrize("subject", ["abc", "", "-1", "1.5", "٣", 1])
def test_correctly_signed_token_with_an_invalid_subject_is_rejected(subject):
    with pytest.raises(InvalidTokenError):
        decode_access_token(sign(valid_claims(sub=subject)))


@pytest.mark.parametrize("role", ["", None, 1, ["admin"]])
def test_correctly_signed_token_with_an_invalid_role_is_rejected(role):
    with pytest.raises(InvalidTokenError):
        decode_access_token(sign(valid_claims(role=role)))
