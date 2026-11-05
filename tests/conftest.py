"""Shared test setup. Tests use an in-memory SQLite database, so MySQL does not need to be running."""

import os

# Set before any app import, and taking priority over .env, so that tests never use real secrets.
os.environ.update({
    "MYSQL_DATABASE": "test_db",
    "MYSQL_USER": "test_user",
    "MYSQL_PASSWORD": "test-password",
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3306",
    "JWT_SECRET_KEY": "test-only-jwt-secret-that-is-long-enough",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
})

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.models import user_model  # noqa: F401  (registers the users table on Base.metadata)


@pytest.fixture
def db():
    # StaticPool: every connection shares one in-memory database, including the test client's thread.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        yield session
    engine.dispose()
