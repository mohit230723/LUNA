"""Global configuration settings for LUNA OS loaded from environment variables."""

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """LUNA runtime configuration settings."""

    FALKORDB_HOST: str = Field(default_factory=lambda: os.getenv("FALKORDB_HOST", "localhost"))
    FALKORDB_PORT: int = Field(default_factory=lambda: int(os.getenv("FALKORDB_PORT", "6379")))
    OLLAMA_BASE_URL: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    OLLAMA_MODEL: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    DEFAULT_RANDOM_SEED: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_RANDOM_SEED", "42")))


settings = Settings()
