from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KE_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    converter: str = "fallback"
    max_upload_mb: int = 25
    ocr_text_coverage_threshold: float = 0.70
    min_quality_score: float = 0.75
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: int = 60
    max_source_chars_per_document: int = 20_000

    @property
    def database_path(self) -> Path:
        return self.data_dir / "knowledge.db"


settings = Settings()
