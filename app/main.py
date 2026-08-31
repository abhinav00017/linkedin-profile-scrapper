"""Application entry point."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router

DESCRIPTION = """
Turn a LinkedIn profile URL into structured JSON.

**How to use it**

1. `POST /v1/auth` with your own LinkedIn `li_at` cookie. You get an API key.
2. `GET /v1/profile?url=…` with that key in the `X-API-Key` header.

Your own LinkedIn session does the reading, so the request budget spent is
yours and nobody else's.

Data comes from two places. The authenticated internal API gives the core
profile. The public page gives experience and education. `meta` on every
response names the sources used and the sections that were not available.
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="LinkedIn Profile API",
        description=DESCRIPTION,
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )
    app.include_router(router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """One error shape everywhere: {"error": {"code", "message"}}."""
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            body = detail
        else:
            body = {"code": "http_error", "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": body})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_request", "message": exc.errors()}},
        )

    return app


app = create_app()
