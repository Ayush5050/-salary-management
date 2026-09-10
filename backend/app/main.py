"""FastAPI application.

Domain errors are translated to HTTP status codes in exactly one place. The
alternative — try/except in every route — spreads the same mapping across the
codebase and lets the two drift apart.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import analytics, employees, query, reference
from app.config import get_settings
from app.errors import (
    DuplicateEmployeeFieldError,
    EmployeeNotFoundError,
    InvalidManagerError,
    SalaryManagementError,
    UnknownReferenceError,
)

settings = get_settings()

app = FastAPI(
    title="ACME Salary Management API",
    version="0.1.0",
    description=(
        "Compensation records and analytics for ACME's HR team. "
        "All monetary values cross this API as integer minor units "
        "(cents, pence, paise) alongside their currency code."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATUS_BY_ERROR: dict[type[SalaryManagementError], int] = {
    EmployeeNotFoundError: status.HTTP_404_NOT_FOUND,
    DuplicateEmployeeFieldError: status.HTTP_409_CONFLICT,
    UnknownReferenceError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidManagerError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@app.exception_handler(SalaryManagementError)
async def handle_domain_error(_request: Request, error: Exception) -> JSONResponse:
    """Map a domain error to its status code, preserving the message.

    Domain messages are written to be shown: they name the offending value and
    the record already holding it, which is what the HR Manager needs to resolve
    a conflict without guessing.
    """
    if not isinstance(error, SalaryManagementError):
        # The handler is registered for SalaryManagementError only; FastAPI's
        # signature is broader, so anything else is re-raised rather than
        # silently reported as a domain problem.
        raise error
    http_status = _STATUS_BY_ERROR.get(type(error), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(
        status_code=http_status,
        content={"detail": str(error), "error": type(error).__name__},
    )


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(employees.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(reference.router, prefix="/api")
app.include_router(query.router, prefix="/api")


def _serve_frontend(static_dir: str) -> None:
    """Serve the built single-page app alongside the API.

    Registered after the API routers so that ``/api/*`` always matches a real
    route first. Deep links such as ``/employees?country=DE`` must return
    ``index.html`` rather than 404 — shareable filtered links are the point of
    keeping filters in the URL — so everything else falls through to the shell.
    """
    static_path = Path(static_dir)
    if not static_path.is_dir():
        raise RuntimeError(
            f"SALARY_STATIC_DIR points at {static_path}, which is not a directory; "
            "build the frontend first or leave the setting unset"
        )

    assets_path = static_path / "assets"
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    index_file = static_path / "index.html"

    @app.get("/{spa_path:path}", include_in_schema=False)
    def serve_spa(spa_path: str) -> FileResponse:
        # An unmatched /api path is a genuine 404, not a page. Returning the
        # HTML shell there would turn a typo'd endpoint into a confusing parse
        # error in the client instead of a clear "no such route".
        if spa_path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no such endpoint: /{spa_path}")
        return FileResponse(index_file)


if settings.static_dir is not None:
    _serve_frontend(settings.static_dir)
