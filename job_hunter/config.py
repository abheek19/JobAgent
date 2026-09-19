import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    gemini_api_key: str
    default_model_fast: str = "gemini-3.5-flash"
    default_model_pro: str = "gemini-3.1-pro-preview"
    app_env: str = "production"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./job_hunt.db"
    csv_export_path: str = "Job-Hunt-Master.csv"
    n8n_scraper_webhook_url: Optional[str] = "http://localhost:5678/webhook/job-scraper"
    port: int = 8000
    host: str = "0.0.0.0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def sync_api_key_to_env(self) -> "Settings":
        """
        Export GEMINI_API_KEY to os.environ so that lang-chain and google-genai
        can automatically pick it up without explicit parameterization everywhere.
        """
        if self.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = self.gemini_api_key
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
