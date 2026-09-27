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
    vision_ocr_api_key: str = ""
    vision_ocr_base_url: str = "https://api.groq.com/openai/v1"
    vision_ocr_model: str = ""
    vision_ocr_timeout_seconds: int = 90
    vision_ocr_max_tokens: int = 4096
    vision_ocr_max_pages: int = 25
    vision_ocr_dpi: int = 180
    publication_dir: Path = Path("published")
    raw_chunk_chars: int = 1_500
    raw_chunk_overlap: int = 150

    @property
    def database_path(self) -> Path:
        return self.data_dir / "knowledge.db"

    @property
    def publication_path(self) -> Path:
        if self.publication_dir.is_absolute():
            return self.publication_dir
        return self.data_dir / self.publication_dir


settings = Settings()
