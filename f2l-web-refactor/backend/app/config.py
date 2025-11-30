"""
Application configuration management using Pydantic Settings.
Loads configuration from environment variables.
"""
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "F2L Sync"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # API
    API_V1_PREFIX: str = "/api/v1"
    WORKERS: int = Field(default=4, ge=1, le=16)

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://f2luser:password@localhost:5432/f2l_sync",
        description="PostgreSQL connection string"
    )
    DATABASE_POOL_SIZE: int = Field(default=20, ge=5, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    REDIS_CACHE_TTL: int = Field(default=3600, ge=60, le=86400, description="Cache TTL in seconds")

    # Celery
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL"
    )
    CELERY_TASK_TIME_LIMIT: int = Field(default=3600, ge=60, description="Task time limit in seconds")
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=3000, ge=30, description="Soft time limit in seconds")

    # Security
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Secret key for general encryption (generate with: secrets.token_urlsafe(32))"
    )
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT signing key (generate with: secrets.token_urlsafe(32))"
    )
    ENCRYPTION_KEY: str = Field(
        ...,
        description="Fernet encryption key for passwords (generate with: Fernet.generate_key())"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=15, le=1440)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost", "http://localhost:3000"],
        description="Allowed CORS origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = Field(default=100, ge=10, le=1000)

    # File Upload
    MAX_UPLOAD_SIZE: int = Field(default=100 * 1024 * 1024, description="Max upload size in bytes (100MB)")

    # Sync Settings
    DEFAULT_SCAN_WORKERS: int = Field(default=5, ge=1, le=20)
    DEFAULT_TRANSFER_WORKERS: int = Field(default=3, ge=1, le=10)
    SCAN_CACHE_ENABLED: bool = True
    SCAN_CACHE_TTL_HOURS: int = Field(default=24, ge=1, le=168)

    # Health Check
    HEALTH_CHECK_INTERVAL_SECONDS: int = Field(default=30, ge=10, le=300)

    # AWS S3 Defaults (Optional)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"

    # Monitoring
    PROMETHEUS_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None

    # Logging
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE_PATH: Optional[str] = None
    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024, description="Max log file size in bytes (10MB)")
    LOG_BACKUP_COUNT: int = Field(default=5, ge=1, le=20)
    LOG_TO_CONSOLE: bool = True
    LOG_TO_FILE: bool = False

    # Temporary Files
    TEMP_DIR: str = Field(default="/tmp/f2l_sync", description="Temporary directory for file transfers")
    TEMP_FILE_CLEANUP_HOURS: int = Field(default=1, ge=1, le=24)

    # Connection Timeouts
    FTP_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=300)
    SFTP_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=300)
    S3_TIMEOUT_SECONDS: int = Field(default=60, ge=10, le=600)
    HTTP_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=300)

    # Retry Settings
    MAX_RETRY_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    RETRY_DELAY_SECONDS: int = Field(default=5, ge=1, le=60)
    EXPONENTIAL_BACKOFF: bool = True

    # Performance Settings
    CHUNK_SIZE_BYTES: int = Field(default=8192, ge=1024, le=1024*1024, description="File transfer chunk size")
    MAX_CONCURRENT_TRANSFERS: int = Field(default=5, ge=1, le=20)
    PROGRESS_UPDATE_INTERVAL: int = Field(default=1, ge=1, le=10, description="Progress update interval in seconds")

    # Maintenance
    CLEANUP_ENABLED: bool = True
    CLEANUP_INTERVAL_HOURS: int = Field(default=24, ge=1, le=168)
    KEEP_EXECUTIONS_DAYS: int = Field(default=30, ge=1, le=365)
    KEEP_LOGS_DAYS: int = Field(default=7, ge=1, le=30)
    KEEP_CACHE_HOURS: int = Field(default=24, ge=1, le=168)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.APP_ENV == "development"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.APP_ENV == "staging"

    def get_database_config(self) -> dict:
        """Get database configuration dictionary."""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "echo": self.DATABASE_ECHO and self.is_development
        }

    def get_redis_config(self) -> dict:
        """Get Redis configuration dictionary."""
        return {
            "url": self.REDIS_URL,
            "cache_ttl": self.REDIS_CACHE_TTL
        }

    def get_celery_config(self) -> dict:
        """Get Celery configuration dictionary."""
        return {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "task_time_limit": self.CELERY_TASK_TIME_LIMIT,
            "task_soft_time_limit": self.CELERY_TASK_SOFT_TIME_LIMIT
        }

    def get_cors_config(self) -> dict:
        """Get CORS configuration dictionary."""
        return {
            "allow_origins": self.CORS_ORIGINS,
            "allow_credentials": self.CORS_ALLOW_CREDENTIALS,
            "allow_methods": self.CORS_ALLOW_METHODS,
            "allow_headers": self.CORS_ALLOW_HEADERS
        }

    def get_logging_config(self) -> dict:
        """Get logging configuration dictionary."""
        return {
            "level": self.LOG_LEVEL,
            "format": self.LOG_FORMAT,
            "file_path": self.LOG_FILE_PATH,
            "max_bytes": self.LOG_MAX_BYTES,
            "backup_count": self.LOG_BACKUP_COUNT,
            "to_console": self.LOG_TO_CONSOLE,
            "to_file": self.LOG_TO_FILE
        }

    def validate_required_settings(self) -> List[str]:
        """
        Validate that all required settings are properly configured.

        Returns:
            List of validation error messages
        """
        errors = []

        # Check required secret keys
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters long")

        if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters long")

        if not self.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY is required for password encryption")

        # Validate database URL
        if not self.DATABASE_URL.startswith(('postgresql://', 'postgresql+asyncpg://')):
            errors.append("DATABASE_URL must be a valid PostgreSQL connection string")

        # Validate Redis URL
        if not self.REDIS_URL.startswith('redis://'):
            errors.append("REDIS_URL must be a valid Redis connection string")

        # Production-specific validations
        if self.is_production:
            if self.DEBUG:
                errors.append("DEBUG should be False in production")

            if self.DATABASE_ECHO:
                errors.append("DATABASE_ECHO should be False in production")

            if not self.SENTRY_DSN:
                errors.append("SENTRY_DSN should be configured in production for error tracking")

        return errors


# Global settings instance
settings = Settings()
