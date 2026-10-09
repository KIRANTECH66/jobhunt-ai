"""Application configuration.

All settings come from environment variables (or a local ``.env`` file loaded by
the container). Secrets never land in source control; this module only holds the
*shapes* of the settings and their defaults.

The settings are intentionally unprefixed so the values in ``.env.example``
match the PRD (section 14) exactly. SQLite is the default database so the app
runs locally without a Postgres instance; ``DATABASE_URL`` pointing at a
PostgreSQL DSN switches to the deployed configuration.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the JobHunt AI backend."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application --------------------------------------------------------
    app_name: str = Field(default="JobHunt AI")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # --- Database -----------------------------------------------------------
    # SQLite by default for local development; a Postgres DSN overrides this.
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/jobhunt.db",
        description=(
            "Async SQLAlchemy URL for application tables. "
            "sqlite+aiosqlite:///... for local runs; postgresql+asyncpg://... for deployed use."
        ),
    )
    # DEPRECATED: reserved for the future LangGraph checkpoint saver. The
    # orchestration milestone wires this; Milestone 1 never uses it.
    checkpoint_dsn: str = Field(
        default="",
        description="Reserved DSN for the future LangGraph checkpoint saver.",
    )

    # --- LLM ----------------------------------------------------------------
    # A single configured LLM provider behind a model adapter. The app never
    # hardcodes an API key and never assumes a particular model is available.
    model_provider: str = Field(default="openai", description="LLM provider name.")
    model_name: str = Field(default="gpt-4o", description="Default chat model name.")
    model_api_key: str = Field(default="", description="Provider API key.")
    model_base_url: str = Field(
        default="", description="Optional provider-compatible base URL."
    )
    model_timeout_seconds: float = Field(default=60.0, ge=1.0)
    model_max_retries: int = Field(default=3, ge=0)
    # When true, the model adapter returns canned responses and never calls a
    # provider. Used by tests and local runs without credentials.
    model_mock: bool = Field(default=False)

    # --- Agent harness ------------------------------------------------------
    max_agent_retries: int = Field(default=2, ge=0, description="Bounded retries for transient agent failures.")
    agent_timeout_seconds: float = Field(default=60.0, ge=1.0)

    # --- Application workflow ----------------------------------------------
    max_revisions: int = Field(default=2, ge=0, description="Max automatic revision attempts per review cycle.")
    job_match_threshold: float = Field(
        default=60.0, ge=0.0, le=100.0,
        description="Minimum match score for application-preparation recommendation.",
    )

    # --- Matching weights (FR-04) ------------------------------------------
    weight_skills: float = Field(default=0.35, description="Weight for relevant skills and experience.")
    weight_role: float = Field(default=0.25, description="Weight for role and responsibility alignment.")
    weight_seniority: float = Field(default=0.15, description="Weight for seniority alignment.")
    weight_location: float = Field(default=0.10, description="Weight for location and work arrangement.")
    weight_compensation: float = Field(default=0.10, description="Weight for compensation alignment when known.")
    weight_industry: float = Field(default=0.05, description="Weight for industry or domain preference.")

    # --- Job sources --------------------------------------------------------
    # Comma-separated list of permitted source identifiers. Empty means no
    # source is configured and ingestion returns a clear configuration error
    # rather than fabricating live results.
    job_sources: str = Field(
        default="fixture",
        description="Comma-separated permitted job-source identifiers.",
    )
    fixture_jobs_path: str = Field(
        default="data/fixtures/jobs.json",
        description="Path to the deterministic fixture job file.",
    )

    # --- Rate limiting ------------------------------------------------------
    rate_limit_per_minute: int = Field(default=60, ge=1)

    # --- Dev auth -----------------------------------------------------------
    # Simple bearer-token auth for the dev milestone. Real auth replaces this.
    dev_auth_token: str = Field(default="dev-token")

    # --- Storage ------------------------------------------------------------
    storage_backend: str = Field(default="local")
    storage_local_dir: str = Field(default="./data/storage")


settings = Settings()