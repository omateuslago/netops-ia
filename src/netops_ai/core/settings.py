"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from netops_ai import __version__


class Settings(BaseSettings):
    """Validated settings loaded from NETOPS_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NETOPS_",
        extra="ignore",
    )

    app_name: str = "NetOps AI"
    app_version: str = __version__
    environment: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = Field(default="/api/v1", pattern=r"^/[a-zA-Z0-9/_-]+$")
    knowledge_dir: Path = Path("knowledge")
    data_dir: Path = Path("data")
    model_cache_dir: Path = Path("data/models")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=100, gt=0)
    max_extracted_chars: int = Field(default=250_000, gt=0)
    chunk_size: int = Field(default=900, ge=100, le=5000)
    chunk_overlap: int = Field(default=150, ge=0)
    token_pipeline: Literal["pdf-token-v1", "pdf-token-v2"] = "pdf-token-v1"
    embedding_threads: int = Field(default=2, ge=1, le=16)
    embedding_batch_size: int = Field(default=8, ge=1, le=64)
    model_local_files_only: bool = False
    max_index_chunks: int = Field(default=2000, ge=1, le=10_000)
    ollama_model: str = ""

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap deve ser menor que chunk_size")
        return self


@lru_cache
def get_settings() -> Settings:
    """Load settings once for the process lifetime."""
    return Settings()
