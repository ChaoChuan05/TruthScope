from functools import lru_cache

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
    GONKA_BASE_URL: HttpUrl = HttpUrl("https://api.gonkarouter.io")
    GONKA_API_KEY: str | None = None
    GONKA_ORCHESTRATOR_MODEL: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_MODEL_A: str = "moonshotai/Kimi-K2.6"
    GONKA_MODEL_B: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_JUDGE_MODEL: str = "deepseek-ai/DeepSeek-V4-Flash-0731"
    GONKA_BIAS_AUDITOR_MODEL: str = "MiniMaxAI/MiniMax-M2.7"
    GONKA_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=600)
    GONKA_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    GONKA_MAX_TOKENS: int = Field(default=2048, ge=1024, le=4096)
    GONKA_PARALLEL_VERIFIERS: bool = False
    GONKA_VERIFIER_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=600)
    GONKA_VERIFIER_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    GONKA_JUDGE_TIMEOUT_SECONDS: float = Field(default=75.0, gt=0, le=600)
    GONKA_JUDGE_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    GONKA_AUDIT_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0, le=600)
    GONKA_AUDIT_MAX_RETRIES: int = Field(default=1, ge=0, le=5)
    MAX_EVIDENCE_PER_CLAIM: int = Field(default=12, ge=1, le=50)
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

    @model_validator(mode="after")
    def gonkaModelsMustBeDistinct(self) -> "Settings":
        configuredModels = {
            self.GONKA_MODEL_A,
            self.GONKA_MODEL_B,
            self.GONKA_JUDGE_MODEL,
        }
        if len(configuredModels) != 3:
            raise ValueError("Gonka verifier A, verifier B, and judge models must be distinct.")
        return self


@lru_cache
def getSettings() -> Settings:
    return Settings()
