"""
Configuration Manager - Advanced configuration management and validation.
"""
import os
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet

from app.config import settings


logger = logging.getLogger(__name__)


class ConfigManager:
    """Advanced configuration management with validation and key generation."""

    def __init__(self):
        """Initialize configuration manager."""
        self.settings = settings

    def validate_configuration(self, raise_on_error: bool = True) -> List[str]:
        """
        Validate all configuration settings.
        
        Args:
            raise_on_error: Whether to raise exception on validation errors
            
        Returns:
            List of validation error messages
            
        Raises:
            ValueError: If validation fails and raise_on_error is True
        """
        errors = self.settings.validate_required_settings()
        
        # Additional validations
        errors.extend(self._validate_directories())
        errors.extend(self._validate_encryption_key())
        errors.extend(self._validate_timeouts())
        errors.extend(self._validate_performance_settings())
        
        if errors and raise_on_error:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            raise ValueError(error_msg)
        
        return errors

    def _validate_directories(self) -> List[str]:
        """Validate directory settings."""
        errors = []
        
        # Check temp directory
        temp_dir = Path(self.settings.TEMP_DIR)
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            if not temp_dir.is_dir():
                errors.append(f"TEMP_DIR is not a valid directory: {self.settings.TEMP_DIR}")
            elif not os.access(temp_dir, os.W_OK):
                errors.append(f"TEMP_DIR is not writable: {self.settings.TEMP_DIR}")
        except Exception as e:
            errors.append(f"Cannot create TEMP_DIR {self.settings.TEMP_DIR}: {e}")
        
        # Check log file directory if specified
        if self.settings.LOG_FILE_PATH:
            log_file = Path(self.settings.LOG_FILE_PATH)
            log_dir = log_file.parent
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                if not log_dir.is_dir():
                    errors.append(f"Log directory is not valid: {log_dir}")
                elif not os.access(log_dir, os.W_OK):
                    errors.append(f"Log directory is not writable: {log_dir}")
            except Exception as e:
                errors.append(f"Cannot create log directory {log_dir}: {e}")
        
        return errors

    def _validate_encryption_key(self) -> List[str]:
        """Validate encryption key format."""
        errors = []
        
        try:
            # Try to create Fernet instance to validate key
            if self.settings.ENCRYPTION_KEY:
                Fernet(self.settings.ENCRYPTION_KEY.encode())
        except Exception as e:
            errors.append(f"ENCRYPTION_KEY is not a valid Fernet key: {e}")
        
        return errors

    def _validate_timeouts(self) -> List[str]:
        """Validate timeout settings."""
        errors = []
        
        # Check that soft timeout is less than hard timeout
        if self.settings.CELERY_TASK_SOFT_TIME_LIMIT >= self.settings.CELERY_TASK_TIME_LIMIT:
            errors.append("CELERY_TASK_SOFT_TIME_LIMIT must be less than CELERY_TASK_TIME_LIMIT")
        
        return errors

    def _validate_performance_settings(self) -> List[str]:
        """Validate performance-related settings."""
        errors = []
        
        # Check worker counts
        if self.settings.DEFAULT_SCAN_WORKERS > self.settings.MAX_CONCURRENT_TRANSFERS * 2:
            errors.append("DEFAULT_SCAN_WORKERS should not be more than 2x MAX_CONCURRENT_TRANSFERS")
        
        return errors

    def generate_secret_keys(self) -> Dict[str, str]:
        """
        Generate secure secret keys for the application.
        
        Returns:
            Dictionary with generated keys
        """
        keys = {
            'SECRET_KEY': secrets.token_urlsafe(32),
            'JWT_SECRET_KEY': secrets.token_urlsafe(32),
            'ENCRYPTION_KEY': Fernet.generate_key().decode()
        }
        
        return keys

    def create_env_file(self, file_path: str = ".env", overwrite: bool = False) -> bool:
        """
        Create .env file with default configuration.
        
        Args:
            file_path: Path to .env file
            overwrite: Whether to overwrite existing file
            
        Returns:
            True if file was created, False if it already exists and overwrite=False
        """
        env_file = Path(file_path)
        
        if env_file.exists() and not overwrite:
            logger.warning(f"Environment file already exists: {file_path}")
            return False
        
        # Generate secret keys
        keys = self.generate_secret_keys()
        
        # Create environment file content
        env_content = f"""# F2L Sync Application Configuration
# Generated on {os.environ.get('HOSTNAME', 'localhost')} at {os.popen('date').read().strip()}

# Application Settings
APP_NAME=F2L Sync
APP_VERSION=2.0.0
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# API Settings
API_V1_PREFIX=/api/v1
WORKERS=4

# Database Settings
DATABASE_URL=postgresql://f2luser:password@localhost:5432/f2l_sync
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_ECHO=false

# Redis Settings
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Celery Settings
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_TIME_LIMIT=3600
CELERY_TASK_SOFT_TIME_LIMIT=3000

# Security Settings (CHANGE THESE IN PRODUCTION!)
SECRET_KEY={keys['SECRET_KEY']}
JWT_SECRET_KEY={keys['JWT_SECRET_KEY']}
ENCRYPTION_KEY={keys['ENCRYPTION_KEY']}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS Settings
CORS_ORIGINS=http://localhost,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=*
CORS_ALLOW_HEADERS=*

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=100

# File Upload
MAX_UPLOAD_SIZE=104857600

# Sync Settings
DEFAULT_SCAN_WORKERS=5
DEFAULT_TRANSFER_WORKERS=3
SCAN_CACHE_ENABLED=true
SCAN_CACHE_TTL_HOURS=24

# Health Check
HEALTH_CHECK_INTERVAL_SECONDS=30

# AWS S3 (Optional)
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# Monitoring (Optional)
PROMETHEUS_ENABLED=false
# SENTRY_DSN=your_sentry_dsn

# Logging
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
# LOG_FILE_PATH=/var/log/f2l_sync/app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
LOG_TO_CONSOLE=true
LOG_TO_FILE=false

# Temporary Files
TEMP_DIR=/tmp/f2l_sync
TEMP_FILE_CLEANUP_HOURS=1

# Connection Timeouts
FTP_TIMEOUT_SECONDS=30
SFTP_TIMEOUT_SECONDS=30
S3_TIMEOUT_SECONDS=60
HTTP_TIMEOUT_SECONDS=30

# Retry Settings
MAX_RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=5
EXPONENTIAL_BACKOFF=true

# Performance Settings
CHUNK_SIZE_BYTES=8192
MAX_CONCURRENT_TRANSFERS=5
PROGRESS_UPDATE_INTERVAL=1

# Maintenance
CLEANUP_ENABLED=true
CLEANUP_INTERVAL_HOURS=24
KEEP_EXECUTIONS_DAYS=30
KEEP_LOGS_DAYS=7
KEEP_CACHE_HOURS=24
"""
        
        try:
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            logger.info(f"Environment file created: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create environment file {file_path}: {e}")
            return False

    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current configuration.
        
        Returns:
            Dictionary with configuration summary
        """
        return {
            'application': {
                'name': self.settings.APP_NAME,
                'version': self.settings.APP_VERSION,
                'environment': self.settings.APP_ENV,
                'debug': self.settings.DEBUG,
                'log_level': self.settings.LOG_LEVEL
            },
            'database': {
                'url_masked': self._mask_url(self.settings.DATABASE_URL),
                'pool_size': self.settings.DATABASE_POOL_SIZE,
                'max_overflow': self.settings.DATABASE_MAX_OVERFLOW,
                'echo': self.settings.DATABASE_ECHO
            },
            'redis': {
                'url_masked': self._mask_url(self.settings.REDIS_URL),
                'cache_ttl': self.settings.REDIS_CACHE_TTL
            },
            'celery': {
                'broker_url_masked': self._mask_url(self.settings.CELERY_BROKER_URL),
                'result_backend_masked': self._mask_url(self.settings.CELERY_RESULT_BACKEND),
                'task_time_limit': self.settings.CELERY_TASK_TIME_LIMIT,
                'task_soft_time_limit': self.settings.CELERY_TASK_SOFT_TIME_LIMIT
            },
            'security': {
                'jwt_algorithm': self.settings.JWT_ALGORITHM,
                'jwt_access_token_expire_minutes': self.settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
                'jwt_refresh_token_expire_days': self.settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
                'secret_key_configured': bool(self.settings.SECRET_KEY),
                'jwt_secret_key_configured': bool(self.settings.JWT_SECRET_KEY),
                'encryption_key_configured': bool(self.settings.ENCRYPTION_KEY)
            },
            'performance': {
                'workers': self.settings.WORKERS,
                'default_scan_workers': self.settings.DEFAULT_SCAN_WORKERS,
                'default_transfer_workers': self.settings.DEFAULT_TRANSFER_WORKERS,
                'max_concurrent_transfers': self.settings.MAX_CONCURRENT_TRANSFERS,
                'chunk_size_bytes': self.settings.CHUNK_SIZE_BYTES
            },
            'timeouts': {
                'ftp_timeout_seconds': self.settings.FTP_TIMEOUT_SECONDS,
                'sftp_timeout_seconds': self.settings.SFTP_TIMEOUT_SECONDS,
                's3_timeout_seconds': self.settings.S3_TIMEOUT_SECONDS,
                'http_timeout_seconds': self.settings.HTTP_TIMEOUT_SECONDS
            },
            'maintenance': {
                'cleanup_enabled': self.settings.CLEANUP_ENABLED,
                'cleanup_interval_hours': self.settings.CLEANUP_INTERVAL_HOURS,
                'keep_executions_days': self.settings.KEEP_EXECUTIONS_DAYS,
                'keep_logs_days': self.settings.KEEP_LOGS_DAYS,
                'keep_cache_hours': self.settings.KEEP_CACHE_HOURS
            },
            'monitoring': {
                'prometheus_enabled': self.settings.PROMETHEUS_ENABLED,
                'sentry_configured': bool(self.settings.SENTRY_DSN)
            }
        }

    def _mask_url(self, url: str) -> str:
        """
        Mask sensitive information in URLs.
        
        Args:
            url: URL to mask
            
        Returns:
            Masked URL string
        """
        if not url:
            return ""
        
        # Simple masking - replace password with asterisks
        import re
        
        # Pattern to match URLs with credentials
        pattern = r'(://[^:]+:)([^@]+)(@)'
        masked = re.sub(pattern, r'\1***\3', url)
        
        return masked

    def check_environment_health(self) -> Dict[str, Any]:
        """
        Check the health of the environment configuration.
        
        Returns:
            Dictionary with health check results
        """
        health = {
            'overall_status': 'healthy',
            'checks': {},
            'warnings': [],
            'errors': []
        }
        
        # Validate configuration
        try:
            validation_errors = self.validate_configuration(raise_on_error=False)
            if validation_errors:
                health['errors'].extend(validation_errors)
                health['overall_status'] = 'unhealthy'
        except Exception as e:
            health['errors'].append(f"Configuration validation failed: {e}")
            health['overall_status'] = 'unhealthy'
        
        # Check directory permissions
        try:
            temp_dir = Path(self.settings.TEMP_DIR)
            temp_dir.mkdir(parents=True, exist_ok=True)
            health['checks']['temp_directory'] = 'accessible'
        except Exception as e:
            health['checks']['temp_directory'] = f'error: {e}'
            health['errors'].append(f"Temp directory not accessible: {e}")
            health['overall_status'] = 'unhealthy'
        
        # Check production readiness
        if self.settings.is_production:
            if self.settings.DEBUG:
                health['warnings'].append("DEBUG is enabled in production")
            
            if not self.settings.SENTRY_DSN:
                health['warnings'].append("SENTRY_DSN not configured for production error tracking")
            
            if self.settings.LOG_LEVEL == 'DEBUG':
                health['warnings'].append("LOG_LEVEL is DEBUG in production")
        
        # Set overall status based on errors
        if health['errors']:
            health['overall_status'] = 'unhealthy'
        elif health['warnings']:
            health['overall_status'] = 'warning'
        
        return health


# Global configuration manager instance
config_manager = ConfigManager()
