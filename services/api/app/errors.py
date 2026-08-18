"""Uniform problem+json error responses (ARCHITECTURE.md §5).

Without this, FastAPI answers 404 with {"detail": ...} and 422 with a nested
validation structure — two shapes the client would have to special-case.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import Problem

CONTENT_TYPE = "application/problem+json"

TITLES = {
    400: "Gecersiz istek",
    404: "Bulunamadi",
    422: "Dogrulama hatasi",
    500: "Sunucu hatasi",
}


def _response(problem: Problem) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=CONTENT_TYPE,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return _response(
            Problem(
                title=TITLES.get(exc.status_code, "Hata"),
                status=exc.status_code,
                detail=detail,
                instance=str(request.url.path),
            )
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else None
        detail = None
        if first:
            location = ".".join(str(part) for part in first.get("loc", ()) if part != "query")
            detail = f"{location}: {first.get('msg')}" if location else first.get("msg")

        return _response(
            Problem(
                title=TITLES[422],
                status=422,
                detail=detail,
                instance=str(request.url.path),
            )
        )
