"""SQLAlchemy ORM models for users.

alembic/env.py imports this module so that Alembic can detect its tables.
"""

import re
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.email_utils import normalize_email
from app.database.connection import Base

DEFAULT_ROLE = "USER"

BCRYPT_HASH_PATTERN = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")


class User(Base):
    __tablename__ = "users"
    # Load database-generated timestamps on flush. Sessions may be closed before they are read.
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Binary collation on MySQL: the default collation would treat "josé@" and "jose@" as the
    # same address. Addresses are lowercased first, so comparisons are still case-insensitive.
    email: Mapped[str] = mapped_column(
        String(255).with_variant(String(255, collation="utf8mb4_bin"), "mysql"),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DEFAULT_ROLE, server_default=DEFAULT_ROLE
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return normalize_email(value)

    @validates("password_hash")
    def _require_password_hash(self, _key: str, value: str) -> str:
        # Last line of defense against a plaintext password reaching the database.
        # The value is deliberately left out of the error message.
        if not BCRYPT_HASH_PATTERN.fullmatch(value):
            raise ValueError("password_hash must be a bcrypt hash")
        return value
