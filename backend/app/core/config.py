from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ALLOWED_ORIGINS: str = "http://127.0.0.1:5500,http://localhost:5500"
    GONKA_BASE_URL: HttpUrl = HttpUrl("https://api.gonkarouter.io")
    GONKA_API_KEY: str | None = None
    GONKA_ORCHESTRATOR_MODEL: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_MODEL_A: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_MODEL_B: str = "deepseek-ai/DeepSeek-V4-Flash-0731"
    GONKA_JUDGE_MODEL: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_BIAS_AUDITOR_MODEL: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=600)
    GONKA_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    GONKA_MAX_TOKENS: int = Field(default=2048, ge=1024, le=4096)
    GONKA_PARALLEL_VERIFIERS: bool = False
    GONKA_REDUCED_CALLS: bool = True
    GONKA_VERIFIER_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=600)
    GONKA_VERIFIER_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    GONKA_VERIFIER_STAGE_TIMEOUT_SECONDS: float = Field(default=180.0, gt=0, le=900)
    GONKA_JUDGE_TIMEOUT_SECONDS: float = Field(default=75.0, gt=0, le=600)
    GONKA_JUDGE_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    GONKA_AUDIT_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0, le=600)
    GONKA_AUDIT_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    GONKA_AUDIT_STAGE_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=900)
    MAX_EVIDENCE_QUERIES_PER_CLAIM: int = Field(default=1, ge=1, le=10)
    MAX_EVIDENCE_PER_CLAIM: int = Field(default=6, ge=1, le=50)
    MAX_TOTAL_EVIDENCE: int = Field(default=8, ge=1, le=100)
    MAX_INPUT_CHARS: int = Field(default=5000, ge=100, le=50_000)
    BRAVE_SEARCH_BASE_URL: HttpUrl = HttpUrl("https://api.search.brave.com")
    BRAVE_SEARCH_API_KEY: str | None = None
    BRAVE_SEARCH_COUNTRY: str = Field(default="MY", pattern=r"^[A-Z]{2}$")
    BRAVE_SEARCH_LANGUAGE: str = Field(default="en", pattern=r"^[a-z]{2,3}$")
    BRAVE_SEARCH_RESULTS_PER_QUERY: int = Field(default=3, ge=1, le=10)
    SUPABASE_URL: HttpUrl | None = None
    SUPABASE_KEY: str | None = None

    @field_validator(
        "GONKA_API_KEY",
        "BRAVE_SEARCH_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        mode="before",
    )
    @classmethod
    def blankOptionalSettingBecomesNone(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def gonkaConfigured(self) -> bool:
        return bool(self.GONKA_API_KEY and self.GONKA_API_KEY.strip())

    @property
    def searchConfigured(self) -> bool:
        return bool(self.BRAVE_SEARCH_API_KEY and self.BRAVE_SEARCH_API_KEY.strip())

    @property
    def supabaseConfigured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_KEY and self.SUPABASE_KEY.strip())

    @property
    def corsAllowedOrigins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def corsOriginsMustBeExplicitHttpOrigins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("At least one CORS origin is required.")

        for origin in origins:
            parsedOrigin = urlsplit(origin)
            if (
                parsedOrigin.scheme not in {"http", "https"}
                or not parsedOrigin.netloc
                or parsedOrigin.path
                or parsedOrigin.query
                or parsedOrigin.fragment
                or parsedOrigin.username
                or parsedOrigin.password
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths.")

        return ",".join(dict.fromkeys(origins))

    @model_validator(mode="after")
    def gonkaVerifierModelsMustBeDistinct(self) -> "Settings":
        if self.GONKA_MODEL_A == self.GONKA_MODEL_B:
            raise ValueError("Gonka verifier A and verifier B models must be distinct.")
        return self


@lru_cache
def getSettings() -> Settings:
    return Settings()
