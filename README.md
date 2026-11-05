# ShopEase Auth Service

Independent FastAPI microservice for ShopEase authentication. It has its own code, configuration, MySQL database, and containers, and it is not integrated with any other ShopEase service.

**Status:** all planned APIs are implemented and tested, including against MySQL in Docker. See [the final completion report](DELIVERABELS/09_Final_Completion_Report.md) for results and remaining work.

## Features

- User registration with email validation, duplicate email prevention, and password strength rules
- Login with JWT access tokens, and the same error for a wrong password and an unknown email
- Current user lookup, token verification, and password changes
- Salted bcrypt password hashing. Passwords and hashes are never returned.
- Protected routes that check the user in the database on every request, so a deactivated or deleted user is rejected at once
- Secrets read from the environment. The service will not start with a missing, too-short, or placeholder secret.
- Alembic migrations, applied automatically when the Docker service starts
- Swagger UI with Bearer authentication
- Consistent error responses that never echo submitted values

## Technology stack

| Area | Choice |
| --- | --- |
| Language | Python 3.11 |
| Web framework | FastAPI 0.162, served by Uvicorn 0.54 |
| Validation and settings | Pydantic 2.14, pydantic-settings 2.16, python-dotenv 1.2, email-validator 2.3 |
| Database | MySQL 8.4 |
| ORM, driver, and migrations | SQLAlchemy 2.1, PyMySQL 1.2, Alembic 1.20 |
| Password hashing | Passlib 1.7.4 with bcrypt 4.0.1 |
| Tokens | python-jose 3.5 with the cryptography backend |
| Testing | pytest 9.2, httpx 0.28 |
| Containers | Docker, Docker Compose |

## Project structure

```text
shopease-auth-service/
├── app/
│   ├── core/                 Settings, password and token security, email normalization
│   ├── database/             Engine, sessions, and the declarative base
│   ├── models/               SQLAlchemy models
│   ├── routers/              HTTP routes
│   ├── schemas/              Pydantic request and response schemas
│   ├── services/             Business logic
│   ├── exception_handlers.py Consistent error responses
│   └── main.py               Application entry point
├── alembic/                  Migration environment and versions
├── tests/                    Automated tests and the live API scenario runner
├── DELIVERABELS/             Project reports and screenshots
├── .env.example              Placeholder settings; copy to .env
├── alembic.ini               Alembic settings, with no credentials
├── docker-compose.yml        The auth-service and auth-mysql services
├── Dockerfile                Application image
├── pytest.ini                Test settings
└── requirements.txt          Pinned dependencies
```

## Environment setup

You need Python 3.11, and Docker Desktop for the database and the containerised stack.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Replace every `change-me` value in `.env`. Generate each secret with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Settings are read from the environment, then from `.env`. Keep real values only in `.env`, which is excluded from Git and Docker images. `.env.example` contains placeholders only.

### Application settings

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APP_NAME` | No | `ShopEase Auth Service` | Name shown in the API documentation and responses |
| `APP_VERSION` | No | `0.1.0` | Version shown in the API documentation and responses |
| `APP_ENV` | No | `development` | Deployment environment name |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `API_PREFIX` | No | `/api` | Prefix for API routes |
| `DOCS_ENABLED` | No | `true` | Serves `/docs`, `/redoc`, and `/openapi.json` when true |
| `AUTH_SERVICE_HOST_PORT` | Docker only | `8001` | Port on this machine for the containerised service |

### JWT settings

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | Yes, secret | None | Token signing secret, at least 32 characters |
| `JWT_ALGORITHM` | No | `HS256` | `HS256`, `HS384`, or `HS512` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifetime, from 1 to 1440 minutes |

### Secret handling

- The service will not start if a required secret is missing, if `JWT_SECRET_KEY` is too short, or if `MYSQL_PASSWORD` or `JWT_SECRET_KEY` still has a `change-me` placeholder value.
- Secrets are masked when settings or the database URL are printed or logged, and rejected values are left out of startup errors.

## MySQL configuration

The service uses its own database, `shopease_auth_db`. The `auth-mysql` container creates the database and user from these settings the first time it starts.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MYSQL_DATABASE` | No | `shopease_auth_db` | Database name |
| `MYSQL_USER` | Yes | None | Database user |
| `MYSQL_PASSWORD` | Yes, secret | None | Database password |
| `MYSQL_HOST` | No | `127.0.0.1` | Database host. Docker Compose sets `auth-mysql` for the container. |
| `MYSQL_PORT` | No | `3306` | Database port. `.env.example` uses `3308`, the port published on this machine. Docker Compose sets `3306` for the container. |
| `MYSQL_ROOT_PASSWORD` | Docker only, secret | None | Root password for the MySQL container. The application does not read it. |

MySQL reads `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_ROOT_PASSWORD` only when its volume is empty. Changing them in `.env` later does not change an existing database.

See [the database schema](DELIVERABELS/05_Database_Schema.md) for the table structure.

## Run on this machine

Start only the database, apply the migrations, and start the API:

```powershell
docker compose up -d auth-mysql --wait
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

The API is then at `http://127.0.0.1:8001`. If the Docker `auth-service` is already running on port 8001, stop it first with `docker compose stop auth-service`, or use a different port.

## Alembic migrations

The Docker service applies migrations when it starts. The commands below are for running on this machine, and need the database to be running. Run them from the project root. Alembic reads the connection from the `MYSQL_*` settings, so `alembic.ini` contains no credentials.

| Command | Effect |
| --- | --- |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic current` | Show the migration applied to the database |
| `alembic check` | Check whether the models and the database differ |
| `alembic downgrade -1` | Undo the most recent migration |
| `alembic revision --autogenerate -m "describe your change"` | Generate a migration after changing a model |

- **Data loss:** undoing the initial migration deletes the `users` table and all its data.
- **Generated files:** review each generated migration before applying it. Autogeneration does not detect changes to column defaults, so write those by hand.

## Run with Docker

Create `.env` first, as shown in [Environment setup](#environment-setup). Then build and start both services:

```powershell
docker compose up -d --build --wait
```

This starts two services:

- **`auth-mysql`:** MySQL 8.4, on `127.0.0.1:3308`. Its data is kept in the named volume `auth_mysql_data`.
- **`auth-service`:** the API, on `http://127.0.0.1:8001`. It connects to MySQL at `auth-mysql:3306`, and reads its JWT and database settings from `.env`.

`auth-service` starts only after `auth-mysql` is healthy. It then runs `alembic upgrade head` once, and starts Uvicorn only if the migrations succeed.

### Docker commands

| Command | Effect |
| --- | --- |
| `docker compose up -d --build --wait` | Build the image, start both services, and wait until they are healthy |
| `docker compose build` | Build the image only |
| `docker compose ps` | Show the status of both services |
| `docker compose logs -f auth-service` | Follow the API logs, including migrations |
| `docker compose logs -f auth-mysql` | Follow the MySQL logs |
| `docker compose restart auth-service` | Restart the API |
| `docker compose exec auth-service alembic current` | Show the migration applied to the database |
| `docker compose stop` | Stop both services and keep the containers |
| `docker compose down` | Remove the containers and keep the data |
| `docker compose down -v` | **Remove the containers and delete all database data** |

### Docker notes

- **Port conflict:** port 8001 is also the default for `auth_service` in the root ShopEase stack. If both run at once, change `AUTH_SERVICE_HOST_PORT` in `.env`.
- **Secrets:** `.env` is excluded from the image by `.dockerignore`. Docker Compose passes its values to the containers at run time.
- **Scaling:** do not start several `auth-service` containers at once without first moving migrations to a separate job, because each container runs them on startup.

See [the Docker execution report](DELIVERABELS/08_Docker_Execution_Report.md) for test results.

## API endpoints

### Authentication

| Method | Path | Bearer token | Success | Errors |
| --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | No | 201 | 409, 422 |
| POST | `/api/auth/login` | No | 200 | 401, 403, 422 |
| GET | `/api/auth/me` | Yes | 200 | 401, 403 |
| POST | `/api/auth/verify-token` | Yes | 200 | 401, 403 |
| POST | `/api/auth/change-password` | Yes | 200 | 400, 401, 403, 422 |

Any endpoint that uses the database returns 503 if MySQL is unavailable.

**Register:** `POST /api/auth/register`

```json
{
  "full_name": "Test User",
  "email": "test.user@example.com",
  "password": "Test!Pass123",
  "confirm_password": "Test!Pass123"
}
```

A password needs at least 8 characters, and an uppercase letter, a lowercase letter, a number, and a special character. It can be at most 72 bytes.

**Log in:** `POST /api/auth/login`

```json
{
  "email": "test.user@example.com",
  "password": "Test!Pass123"
}
```

The response contains the token and the user's profile:

```json
{
  "message": "Login successful",
  "access_token": "<token>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "full_name": "Test User",
    "email": "test.user@example.com",
    "role": "USER",
    "is_active": true
  }
}
```

**Get the current user:** `GET /api/auth/me` has no body. It returns the same fields as `user` above.

**Verify a token:** `POST /api/auth/verify-token` has no body. It returns `"valid": true` and `user`. An invalid token returns 401, so treat any other response than 200 as not verified.

**Change the password:** `POST /api/auth/change-password`

```json
{
  "current_password": "Test!Pass123",
  "new_password": "New!Pass456",
  "confirm_new_password": "New!Pass456"
}
```

The response contains only `"message": "Password changed successfully"`.

### Service

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Service information |
| GET | `/health` | Health check for the API process |
| GET | `/health/db` | Database connectivity check; returns 503 if MySQL is unreachable |
| GET | `/docs` | Swagger UI, when `DOCS_ENABLED=true` |
| GET | `/redoc` | ReDoc, when `DOCS_ENABLED=true` |
| GET | `/openapi.json` | OpenAPI schema, when `DOCS_ENABLED=true` |

See [the API documentation](DELIVERABELS/04_API_Documentation.md) for every field, response, and error.

## JWT authentication

1. Log in to get an `access_token`. It lasts for `ACCESS_TOKEN_EXPIRE_MINUTES`, which is 30 by default.
2. Send it with each protected request, in the header `Authorization: Bearer <token>`.
3. When it expires, the request returns 401. Log in again to get a new one. There are no refresh tokens.

From PowerShell, with the service running:

```powershell
$base = "http://127.0.0.1:8001/api/auth"
$register = @{ full_name = "Test User"; email = "test.user@example.com"; password = "Test!Pass123"; confirm_password = "Test!Pass123" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/register" -ContentType "application/json" -Body $register

$credentials = @{ email = "test.user@example.com"; password = "Test!Pass123" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "$base/login" -ContentType "application/json" -Body $credentials
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Uri "$base/me" -Headers $headers
```

| Response | Meaning |
| --- | --- |
| 401 `Could not validate credentials` | The token is missing, expired, malformed, or invalid, or the user no longer exists |
| 403 `Inactive user` | The token is valid, but the account is deactivated |

Treat a token like a password: do not log it, commit it, or put it in a screenshot. See [the JWT authentication flow](DELIVERABELS/06_JWT_Authentication_Flow.md) for details.

## Swagger UI

1. Start the service, then open `http://127.0.0.1:8001/docs`. The browser needs internet access, because Swagger UI loads its files from a public CDN.
2. Open `POST /api/auth/register`, select **Try it out**, enter a request, and select **Execute**.
3. Do the same with `POST /api/auth/login`, and copy `access_token` from the response.
4. Select **Authorize** at the top of the page, paste the token without the word `Bearer`, select **Authorize**, then **Close**.
5. Call `GET /api/auth/me`, `POST /api/auth/verify-token`, or `POST /api/auth/change-password`. Protected endpoints show a padlock.
6. To send no token, select **Authorize**, then **Logout**.

See [the API testing report](DELIVERABELS/07_API_Testing_Report.md) for full Swagger UI and Postman steps.

## Testing

**Automated tests:** these use an in-memory SQLite database and test-only secrets, so they need neither MySQL nor `.env`.

```powershell
python -m pytest
```

**The 22 mandatory API scenarios against the running containers and MySQL:** this needs `.env`, and the runner deletes its test users afterwards.

```powershell
docker compose up -d --build --wait
python -m tests.run_live_scenarios
```

**Postman:** import the collection and environment from [`DELIVERABELS/postman/`](DELIVERABELS/postman/).

See [the API testing report](DELIVERABELS/07_API_Testing_Report.md) for results and setup steps, and [the screenshots](DELIVERABELS/screenshots/README.md) for evidence.

## Known limitations

- **No rate limiting:** repeated login and password change attempts are not limited. Add this in the service or at an API gateway before production use.
- **No token revocation:** a token cannot be cancelled individually, and tokens issued before a password change keep working until they expire. Deactivating the user is the way to block access sooner.
- **No refresh tokens:** the client must log in again when a token expires.
- **No account management:** nothing in the API deactivates a user or changes a role, so those need a direct database change. There is also no password reset for a forgotten password.
- **Email ownership is not verified:** registration only checks the address format. The 409 response also shows that an address is already registered.
- **No HTTPS:** the service itself serves plain HTTP and its ports are published on this machine only. Put it behind HTTPS before exposing it.
- **One container only:** migrations run when the container starts, so several `auth-service` containers should not start at once.
- **Shared secret:** any service that holds `JWT_SECRET_KEY` can also create valid tokens, so share it as little as possible.
- **Other services:** no other ShopEase microservice is integrated with this one.

### Dependency notes

- **`bcrypt` is pinned to 4.0.1.** Passlib 1.7.4 is not compatible with newer `bcrypt` releases, so retest password hashing before changing this pin.
- **`python-jose` 3.5.0 has an advisory with no fixed release (CVE-2026-85394).** Always pass an explicit `algorithms=[settings.jwt_algorithm]` when decoding tokens. Settings allow HMAC algorithms only.
- **`ecdsa` is installed by `python-jose` and has an advisory with no planned fix (CVE-2024-23342).** It affects ECDSA signing. This service signs tokens with HMAC only.
- **`httpx` with the test client:** Starlette reports a deprecation warning. Tests still run, but `httpx2` will be needed in a future upgrade.
