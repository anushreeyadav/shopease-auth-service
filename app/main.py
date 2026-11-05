"""Application entry point: builds the FastAPI app and registers routes.

Run with:  uvicorn app.main:app --reload --port 8001

Routing: settings.api_prefix ("/api") + the router's own prefix ("/auth")
= /api/auth. Routers only handle HTTP; business logic lives in app/services.
"""

import logging

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import check_database_connection, get_db
from app.exception_handlers import register_exception_handlers
from app.routers import auth_routes
from app.schemas.auth_schema import DatabaseHealthResponse, HealthResponse, RootResponse

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper(),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# debug is deliberately not enabled: in debug mode Starlette sends tracebacks to clients.
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Authentication microservice for ShopEase: registration, login, token verification, "
        "and password changes.\n\n"
        "To call a protected endpoint from this page, log in, select **Authorize**, "
        "and paste the access token."
    ),
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.include_router(auth_routes.router, prefix=settings.api_prefix)
register_exception_handlers(app)


@app.get("/", response_model=RootResponse, tags=["Service"], summary="Service information")
def root():
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        docs_url=app.docs_url,
    )


@app.get("/health", response_model=HealthResponse, tags=["Service"], summary="Health check")
def health():
    return HealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


@app.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    responses={503: {"description": "Database unavailable"}},
    tags=["Service"],
    summary="Database connectivity check",
)
def database_health(db: Session = Depends(get_db)):
    if not check_database_connection(db):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return DatabaseHealthResponse(status="ok", database="connected")
