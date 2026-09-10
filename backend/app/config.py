"""Application configuration.

Field defaults here describe the local development setup so the app runs with no
environment file at all; every value is overridable through ``SALARY_``-prefixed
environment variables in deployed environments.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SALARY_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{_BACKEND_ROOT / 'salary.db'}"
    base_currency: str = "USD"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    sql_echo: bool = False

    static_dir: str | None = None
    """Directory holding the built frontend, if this process should serve it.

    Unset in development, where Vite serves the UI and proxies the API. Set in
    the deployed image so one service answers on one origin, which removes CORS
    from the deployment entirely.
    """

    max_page_size: int = 100
    """Upper bound on ``page_size``.

    A client asking for all 10,000 rows in one response would defeat the
    pagination the whole read path is built around, so the API refuses rather
    than silently truncating.
    """


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings, cached so the environment is read exactly once."""
    return Settings()
