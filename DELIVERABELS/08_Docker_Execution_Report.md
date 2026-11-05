# Docker Execution Report: ShopEase Auth Service

**Date:** 5 November 2026
**Name:** Anushree Yadav
**Result:** Both containers started and became healthy, and the application connected to MySQL. All 38 checks passed on the final run.

## Environment

| Item | Value |
| --- | --- |
| Operating system | Windows 11 Pro with Docker Desktop |
| Docker Compose | 5.3.1 |
| Application image | Built from the project's `Dockerfile`, on `python:3.11-slim-bookworm` |
| Database image | `mysql:8.4`, running server version 8.4.11 |

## Configuration

| Item | Configuration |
| --- | --- |
| Services | `auth-service` and `auth-mysql` |
| Database | `shopease_auth_db`, created by the MySQL container on first start |
| Credentials | Read from `.env`. Compose stops with an error if a required value is missing. |
| Data storage | Named volume `auth_mysql_data`, mounted at `/var/lib/mysql` |
| Database host | `auth-mysql`, the Compose service name |
| Published ports | API on `127.0.0.1:8001`, MySQL on `127.0.0.1:3308`. Both are reachable only from this machine. |
| MySQL readiness | Health check with `mysqladmin ping` over TCP |
| Service startup order | `auth-service` waits until `auth-mysql` is healthy |

## Migration strategy

The container runs one command when it starts:

```text
alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8001
```

- **Migrations run first:** Uvicorn opens port 8001 only after the migrations finish, so the application cannot accept requests before the tables exist.
- **A failed migration stops startup:** because of `&&`, Uvicorn does not start if Alembic fails.
- **No competing migrations:** the container runs Alembic once, then one Uvicorn process with no `--workers` option.
- **Clean shutdown:** `exec` makes Uvicorn process 1, so it receives Docker's stop signal directly.

**Limitation:** this strategy is safe for one `auth-service` container. Several containers starting together could each run migrations. Before scaling out, migrations should move to a separate job that runs once.

## Commands run

```powershell
docker compose up -d --build --wait
docker compose ps
docker compose logs auth-service
docker compose stop auth-service
docker compose down
docker compose up -d --wait
docker compose down -v --rmi local
```

## Startup on an empty volume

| Time | `auth-mysql` | `auth-service` |
| --- | --- | --- |
| 1.4 s | Starting | Created, not running |
| 21.9 s | Healthy | Running, health check starting |
| 27.8 s | Healthy | Healthy |

Service log from the first start, with the health check line omitted:

```text
INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 83f96cff2441, create users table
INFO  [alembic.runtime.migration] Running upgrade 83f96cff2441 -> 12ee6f689116, change default role to USER
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

## Test results

| Area | Check | Result |
| --- | --- | --- |
| Compose | Exactly two services, MySQL 8, `shopease_auth_db`, health check, named volume, health-based wait, `auth-mysql` host | Passed |
| Compose | Refuses to run when `JWT_SECRET_KEY` is empty | Passed |
| Secrets | JWT secret in the container matches `.env` | Passed |
| Secrets | No secret values in `docker-compose.yml` or `Dockerfile` | Passed |
| Image | No `.env` file anywhere in the image. `/app` holds only `alembic`, `alembic.ini`, `app`, and `requirements.txt`. | Passed |
| Image | No secret values in application files, image environment, or image history | Passed |
| Container | Python 3.11, non-root user, Uvicorn as process 1, exactly one Uvicorn process | Passed |
| Connection | Both containers healthy, and `/health/db` reports connected | Passed |
| Connection | Application connected to `shopease_auth_db` on MySQL 8.4.11 | Passed |
| Migrations | Database at the latest revision, `12ee6f689116` | Passed |
| Migrations | Each migration applied once, with none applied again after a restart | Passed |
| API | Register, `/me`, change password, and Swagger UI all worked through the container | Passed |
| Logs | No passwords, tokens, or secrets in service logs, and no secret values in MySQL logs | Passed |
| Shutdown | Service stopped in 0.9 s with exit code 0 | Passed |
| Persistence | `docker compose down` removed the containers and kept the volume | Passed |
| Persistence | After `up`, the changed password still logged in and the old one still failed | Passed |
| Failure | Wrong database password: exit code 1, Uvicorn did not start, no password in the output | Passed |
| Regression | `python -m pytest`, 276 tests | 276 passed, with 1 `httpx` deprecation warning |

## Final audit

Repeated on 5 November 2026, with the image built using `docker compose build --no-cache` and the stack started from an empty volume. All 68 checks in the audit passed. The Docker results were:

| Check | Result |
| --- | --- |
| Build time with no cache | 32 s |
| Time for the stack to become healthy | 28 s |
| Both services running and healthy, connected to MySQL 8.4.11 | Passed |
| 22 mandatory API scenarios | 22 of 22 passed |
| No `.env` anywhere in the image, and no secret values in `/app`, image history, or image configuration | Passed |
| `/app` holds only `alembic`, `alembic.ini`, `app`, and `requirements.txt` | Passed |
| Non-root user, with Uvicorn as process 1 | Passed |
| Restart did not repeat the migrations | Passed |
| A user and their password survived `docker compose down` and `up` | Passed |
| With MySQL stopped, `/health` returned 200, and `/health/db` and login returned 503, followed by a reconnect | Passed |
| No secret values, test passwords, tokens, or hashes in service logs, and no secret values in MySQL logs | Passed |
| Test stack removed, with 6 other containers still running | Passed |

## Issues and resolutions

| Issue | Resolution |
| --- | --- |
| Migrations had to be run by hand after starting the stack | The container now runs them on startup. |
| `APP_NAME`, `APP_VERSION`, and `API_PREFIX` in `.env` did not reach the container | Added to `docker-compose.yml`. |
| On the first run, 1 of 38 checks failed: "Exactly one Uvicorn process" found 2 | The check was counting its own command, which contains the word "uvicorn". After it excluded itself, it found 1 on a rerun from an empty volume. The application was not changed. |

## Not tested

- Starting several `auth-service` containers at once.
- A failed migration under Compose's restart policy. The failure was tested with a single `docker run`. Under Compose, `restart: unless-stopped` is expected to keep retrying until the problem is fixed.

## Current state

The test containers, volume, and image were removed afterwards, so no Auth Service containers are running now. To start the stack again, run `docker compose up -d --build --wait`. Other projects' containers on this machine were not changed.

## Screenshots

See the [screenshots folder](screenshots/README.md), including `02_docker_containers.png`.
