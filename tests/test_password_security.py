"""Unit tests for password hashing, verification, and strength rules."""

import pytest

from app.core.security import hash_password, validate_password_strength, verify_password
from app.models.user_model import User
from app.schemas.auth_schema import UserResponse

PASSWORD = "Str0ng!Password"


def test_hash_is_bcrypt_and_does_not_contain_the_password():
    hashed = hash_password(PASSWORD)
    assert hashed.startswith("$2b$")
    assert PASSWORD not in hashed


def test_same_password_gets_a_different_salted_hash():
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_hash_is_accepted_by_the_user_model():
    assert User(password_hash=hash_password(PASSWORD)).password_hash.startswith("$2b$")


def test_user_model_rejects_a_plaintext_password():
    with pytest.raises(ValueError) as error:
        User(password_hash=PASSWORD)
    assert PASSWORD not in str(error.value)


def test_verify_accepts_the_correct_password():
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


@pytest.mark.parametrize("attempt", ["Str0ng!Passwor", "str0ng!password", "", PASSWORD + " "])
def test_verify_rejects_a_wrong_password(attempt):
    assert verify_password(attempt, hash_password(PASSWORD)) is False


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", PASSWORD, "$2b$12$tooshort"])
def test_verify_returns_false_for_a_malformed_hash(bad_hash):
    assert verify_password(PASSWORD, bad_hash) is False


def test_hash_refuses_a_password_over_72_bytes():
    with pytest.raises(ValueError):
        hash_password("A" * 73)


def test_hash_counts_bytes_not_characters():
    with pytest.raises(ValueError):
        hash_password("é" * 37)  # 37 characters, 74 bytes


def test_72_byte_password_works():
    password = "A" * 72
    assert verify_password(password, hash_password(password)) is True


def test_verify_does_not_match_on_the_first_72_bytes_alone():
    password = "A" * 72
    assert verify_password(password + "extra", hash_password(password)) is False


@pytest.mark.parametrize("password", ["Str0ng!Password", "Abcdef1!", "Pässw0rd!", "A1!" + "b" * 69])
def test_strong_passwords_are_accepted(password):
    validate_password_strength(password)


@pytest.mark.parametrize(
    ("password", "expected_message"),
    [
        ("Ab1!xyz", "at least 8 characters"),
        ("str0ng!password", "uppercase"),
        ("STR0NG!PASSWORD", "lowercase"),
        ("Strong!Password", "number"),
        ("Str0ngPassword", "special character"),
        ("Str0ng Password", "special character"),
        ("A1!" + "b" * 70, "at most 72 bytes"),
        ("Str0ng!Pass\x00word", "null character"),
    ],
)
def test_weak_passwords_are_rejected_with_the_reason(password, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        validate_password_strength(password)


def test_every_unmet_rule_is_reported():
    with pytest.raises(ValueError) as error:
        validate_password_strength("")
    message = str(error.value)
    for rule in ("at least 8", "uppercase", "lowercase", "number", "special"):
        assert rule in message


def test_strength_error_does_not_contain_the_password():
    with pytest.raises(ValueError) as error:
        validate_password_strength("weakpassword")
    assert "weakpassword" not in str(error.value)


def test_user_response_schema_has_no_password_field():
    assert not any("password" in field for field in UserResponse.model_fields)
