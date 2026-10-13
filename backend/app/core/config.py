"""
Configuration management for VISHWAS backend.
Loads settings from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "vishwas-api"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = "sqlite:///./vishwas.db"
    
    # Storage
    upload_dir: str = "./storage/uploads"
    max_upload_size_mb: int = 50
    
    # Allowed file extensions
    allowed_extensions: str = "wav,mp3,m4a"
    
    # CORS
    cors_origins: str = "http://localhost:8501,http://localhost:3000"
    
    # Analysis
    analysis_mode: str = "mock"           # "real" | "mock"
    mock_processing_delay_seconds: int = 2

    # ASR — faster-whisper
    whisper_model_size: str = "base"      # base | small | medium
    whisper_device: str = "cpu"           # cpu | cuda
    whisper_compute_type: str = "int8"    # int8 | float16

    # Voice layer
    enable_voice_layer: bool = True
    voice_min_duration_s: float = 3.0
    voice_min_snr_db: float = 5.0

    # Tier 2 — Agentic AI (Phase 3)
    tier2_enabled: bool = False
    tier2_provider: str = "openai"      # openai | anthropic | local
    tier2_model: str = "gpt-4o-mini"
    tier2_api_key: Optional[str] = None
    tier2_timeout: float = 30.0
    tier2_max_retries: int = 2
    tier2_max_input_tokens: int = 4000
    tier2_max_output_tokens: int = 2000

    # Logging
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Parse allowed extensions into a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Convert max upload size from MB to bytes."""
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
