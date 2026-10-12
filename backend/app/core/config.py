"""
Configuration management for VISHWAS backend.
Loads settings from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


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
    analysis_mode: str = "mock"
    mock_processing_delay_seconds: int = 2
    
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
