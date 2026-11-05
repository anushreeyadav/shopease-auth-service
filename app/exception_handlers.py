"""Exception handlers, so that every error response has the same JSON shape."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _field_name(error: dict) -> str:
    if error["type"] == "json_invalid":
        return "body"
    return ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0])


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Built field by field: FastAPI's default response includes the submitted values, and so
    # would send a rejected password back to the client.
    errors = [
        {"field": _field_name(error), "message": error["msg"].removeprefix("Value error, ")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Validation failed", "errors": errors},
    )


async def _database_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Class name only: driver messages can include connection details.
    logger.error("Database error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service temporarily unavailable"},
    )


async def _unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    # The exception itself is re-raised by Starlette after this response, and logged by the server.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(SQLAlchemyError, _database_error)
    app.add_exception_handler(Exception, _unexpected_error)
