# Database Schema: ShopEase Auth Service

## Database

| Property | Value |
| --- | --- |
| Engine | MySQL 8.4, InnoDB |
| Database | `shopease_auth_db` |
| Character set | `utf8mb4` |
| Migration tool | Alembic |
| Connection settings | `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` |

This database belongs to the Auth Service alone. Other services do not read from it or write to it.

## Table: `users`

| Column | Type | Null | Default | Constraints and notes |
| --- | --- | --- | --- | --- |
| `id` | `INT` | No | Auto-increment | Primary key |
| `full_name` | `VARCHAR(255)` | No | None | |
| `email` | `VARCHAR(255)`, `utf8mb4_bin` | No | None | Unique index `ix_users_email`; stored normalized |
| `password_hash` | `VARCHAR(255)` | No | None | bcrypt hash only |
| `role` | `VARCHAR(50)` | No | `USER` | |
| `is_active` | `BOOLEAN` (`TINYINT(1)`) | No | `1` (true) | |
| `created_at` | `DATETIME` | No | Current time | Set once when the row is inserted |
| `updated_at` | `DATETIME` | No | Current time | Updated by the application on every ORM update |

Structure after applying both migrations:

```sql
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `email` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` varchar(50) NOT NULL DEFAULT 'USER',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

## Data rules

### Email normalization

Addresses are trimmed and lowercased by `normalize_email()` in `app/core/email_utils.py`.

- **Saving:** the `User` model normalizes every address assigned to `email`, so registration cannot store another form.
- **Lookup:** `get_user_by_email()` normalizes its input, so `USER@Example.com` finds `user@example.com`.
- **Uniqueness:** the unique index rejects duplicates in any letter case, because all stored addresses are lowercase.
- **Collation:** `utf8mb4_bin` compares addresses exactly. The MySQL default would treat `josé@example.com` and `jose@example.com` as the same address.

### Passwords

Only bcrypt hashes are stored. The `User` model rejects any `password_hash` value that is not in bcrypt format, and the rejected value is left out of the error message.

### Timestamps

All timestamps are in UTC. The application sets each connection's time zone to UTC, and the database generates the values. They are stored without a time zone, so API responses must treat them as UTC.

`updated_at` changes only through SQLAlchemy updates. A manual SQL `UPDATE` must set it explicitly.

## Database session dependency

`get_db()` in `app/database/connection.py` gives each request its own session:

```python
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

A route requests a session with `db: Session = Depends(get_db)`. Each request then follows these steps:

1. **Before the route:** FastAPI runs `get_db()` up to `yield`, which creates a session. No connection is opened yet.
2. **During the route:** the route receives the session. Its first query borrows a connection from the pool.
3. **After the route:** FastAPI resumes `get_db()` after `yield`.
4. **Cleanup:** the `finally` block closes the session, even if the route raised an exception. Uncommitted work is rolled back, and the connection returns to the pool.

Sessions do not commit automatically, so the service code must call `db.commit()` to save its changes.

## Connectivity validation

`GET /health/db` runs `SELECT 1` through the `get_db()` dependency.

| Database state | Status | Response |
| --- | --- | --- |
| Reachable | 200 | `{"status": "ok", "database": "connected"}` |
| Unreachable | 503 | `{"detail": "Database unavailable"}` |

The response and log message exclude connection details. `GET /health` does not use the database, so it shows whether the API process itself is running.

## Database migrations

Migrations are versioned scripts that change the database structure. They keep the structure in the code repository, so every environment can build the same tables in the same order.

### How Alembic is configured

| File | Purpose |
| --- | --- |
| `alembic.ini` | Script location and logging. It contains no database URL or credentials. |
| `alembic/env.py` | Connects Alembic to the application's engine and model metadata |
| `alembic/script.py.mako` | Template for new migration files |
| `alembic/versions/` | Migration scripts |

`alembic/env.py` reuses the application's configuration in two ways:

- **Connection:** it uses the engine from `app/database/connection.py`, which is built from the `MYSQL_*` settings. Migrations therefore use the same database as the application.
- **Models:** it imports `app/models/user_model.py`, which registers the `users` table on `Base.metadata`. Autogeneration compares this metadata with the live database.

### Initial migration

| Property | Value |
| --- | --- |
| File | `alembic/versions/83f96cff2441_create_users_table.py` |
| Revision | `83f96cff2441` |
| Previous revision | None |
| `upgrade()` | Creates the `users` table and the unique index `ix_users_email` |
| `downgrade()` | Drops the index and the `users` table |

Alembic records the applied revision in its own `alembic_version` table, which stays in the database after a downgrade. That table is how it knows which migrations are still pending.

### Default role migration

| Property | Value |
| --- | --- |
| File | `alembic/versions/12ee6f689116_change_default_role_to_user.py` |
| Revision | `12ee6f689116` |
| Previous revision | `83f96cff2441` |
| `upgrade()` | Sets the `role` default to `USER`, and changes existing `customer` rows to `USER` |
| `downgrade()` | Sets the `role` default to `customer`, and changes all `USER` rows to `customer` |

This migration was written by hand because Alembic's autogeneration is not configured to detect changes to column defaults. `alembic check` therefore does not compare them either.

### Commands

The `auth-service` container runs `alembic upgrade head` each time it starts. To run these commands on this machine, start the database first with `docker compose up -d auth-mysql`.

| Command | Effect |
| --- | --- |
| `alembic revision --autogenerate -m "create users table"` | Compares the models with the database and writes a new migration. Replace the message with a description of the change. |
| `alembic upgrade head` | Applies all pending migrations |
| `alembic downgrade -1` | Undoes the most recent migration. Undoing the initial migration deletes the `users` table and its data. |
| `alembic current` | Shows the revision applied to the database |
| `alembic check` | Reports whether the models and the migrated database differ |

The initial migration already exists, so the autogenerate command is needed only after a model changes. Autogeneration can miss some changes, such as renamed columns, so each generated file must be reviewed before it is applied.

## Validation results

Tested on 4 November 2026 against a running MySQL 8.4.11 container, which was removed afterwards. Alembic used the connection settings from `.env`.

| Check | Result |
| --- | --- |
| Alembic autogeneration detected the table and index | Passed |
| `alembic upgrade head` on an empty database | Created `users` and `ix_users_email`, and recorded revision `83f96cff2441` |
| `alembic check` after upgrading | No differences |
| `alembic downgrade -1` | Dropped `users` and cleared the recorded revision |
| `alembic upgrade head` again | Recreated `users` and `ix_users_email` |
| `alembic current` and `alembic check` inside the API container | Revision `83f96cff2441`, no differences |
| Credentials or database URLs in `alembic.ini`, `alembic/env.py`, and the migration file | None found |
| One-off validation script against MySQL, 30 checks | All passed. This ran before the default role changed to `USER`. |
| `GET /health/db` with MySQL stopped | Returned 503, with no connection details |
| Default role migration on a table with an existing `customer` row | Upgrade set the default and the row to `USER`; downgrade restored `customer`; upgrading again set `USER` |
| `alembic check` after the default role migration | No differences |

### Final audit

Tested on 5 November 2026 on a freshly built stack, which was removed afterwards.

| Check | Result |
| --- | --- |
| Migrations on container startup, on an empty volume | Both applied, reaching `12ee6f689116` |
| Tables after startup | `users` and `alembic_version` |
| `alembic check` in the container and on this machine | No differences |
| `alembic downgrade -1`, from this machine | Passed. The default role returned to `customer`. |
| `alembic downgrade base`, from this machine | Removed `users` |
| `alembic upgrade head`, from this machine | Restored the latest revision |
| Service restart | Migrations were not repeated |
| `docker compose down`, then `up`, on the same volume | A user and their password were kept |
| `GET /health/db` and login with MySQL stopped | Both returned 503, and the service reconnected when MySQL returned |
| Columns in `users` | No plaintext password column, and the submitted password was in no column |
