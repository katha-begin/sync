"""
Logging Configuration - Centralized logging setup with structured logging.
"""
import logging
import logging.handlers
import sys
import json
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Create base log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add process and thread info
        log_entry['process_id'] = record.process
        log_entry['thread_id'] = record.thread
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, default=str)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""

    def __init__(self):
        """Initialize context filter."""
        super().__init__()
        self.context = {}

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context information to log record."""
        # Add context fields to record
        for key, value in self.context.items():
            setattr(record, key, value)
        
        return True

    def set_context(self, **kwargs):
        """Set context information."""
        self.context.update(kwargs)

    def clear_context(self):
        """Clear context information."""
        self.context.clear()


class LoggingManager:
    """Centralized logging management."""

    def __init__(self):
        """Initialize logging manager."""
        self.context_filter = ContextFilter()
        self.configured = False

    def configure_logging(self):
        """Configure application logging."""
        if self.configured:
            return
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Configure console logging
        if settings.LOG_TO_CONSOLE:
            self._configure_console_logging(root_logger)
        
        # Configure file logging
        if settings.LOG_TO_FILE and settings.LOG_FILE_PATH:
            self._configure_file_logging(root_logger)
        
        # Configure third-party loggers
        self._configure_third_party_loggers()
        
        self.configured = True
        
        # Log configuration completion
        logger = logging.getLogger(__name__)
        logger.info("Logging configuration completed", extra={
            'log_level': settings.LOG_LEVEL,
            'log_to_console': settings.LOG_TO_CONSOLE,
            'log_to_file': settings.LOG_TO_FILE,
            'log_file_path': settings.LOG_FILE_PATH
        })

    def _configure_console_logging(self, root_logger: logging.Logger):
        """Configure console logging handler."""
        console_handler = logging.StreamHandler(sys.stdout)
        
        if settings.is_production:
            # Use structured JSON logging in production
            console_handler.setFormatter(StructuredFormatter())
        else:
            # Use human-readable format in development
            formatter = logging.Formatter(
                fmt=settings.LOG_FORMAT,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
        
        console_handler.addFilter(self.context_filter)
        root_logger.addHandler(console_handler)

    def _configure_file_logging(self, root_logger: logging.Logger):
        """Configure file logging handler."""
        try:
            # Create log directory if it doesn't exist
            log_file = Path(settings.LOG_FILE_PATH)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Use rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=settings.LOG_FILE_PATH,
                maxBytes=settings.LOG_MAX_BYTES,
                backupCount=settings.LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            
            # Always use structured JSON for file logging
            file_handler.setFormatter(StructuredFormatter())
            file_handler.addFilter(self.context_filter)
            
            root_logger.addHandler(file_handler)
            
        except Exception as e:
            # Fall back to console logging if file logging fails
            console_logger = logging.getLogger(__name__)
            console_logger.error(f"Failed to configure file logging: {e}")

    def _configure_third_party_loggers(self):
        """Configure third-party library loggers."""
        # Reduce noise from third-party libraries
        third_party_loggers = [
            'urllib3.connectionpool',
            'requests.packages.urllib3',
            'paramiko.transport',
            'paramiko.hostkeys',
            'boto3.resources',
            'botocore.credentials',
            'celery.worker',
            'celery.beat',
            'sqlalchemy.engine',
            'sqlalchemy.pool'
        ]
        
        for logger_name in third_party_loggers:
            logger = logging.getLogger(logger_name)
            if settings.is_production:
                logger.setLevel(logging.WARNING)
            else:
                logger.setLevel(logging.INFO)

    def set_context(self, **kwargs):
        """Set logging context for current thread."""
        self.context_filter.set_context(**kwargs)

    def clear_context(self):
        """Clear logging context for current thread."""
        self.context_filter.clear_context()

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get logger with proper configuration.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger instance
        """
        if not self.configured:
            self.configure_logging()
        
        return logging.getLogger(name)


class AuditLogger:
    """Specialized logger for audit events."""

    def __init__(self):
        """Initialize audit logger."""
        self.logger = logging.getLogger('audit')

    def log_endpoint_created(self, endpoint_id: str, endpoint_type: str, user_id: Optional[str] = None):
        """Log endpoint creation."""
        self.logger.info("Endpoint created", extra={
            'event_type': 'endpoint_created',
            'endpoint_id': endpoint_id,
            'endpoint_type': endpoint_type,
            'user_id': user_id
        })

    def log_endpoint_deleted(self, endpoint_id: str, user_id: Optional[str] = None):
        """Log endpoint deletion."""
        self.logger.info("Endpoint deleted", extra={
            'event_type': 'endpoint_deleted',
            'endpoint_id': endpoint_id,
            'user_id': user_id
        })

    def log_session_started(self, session_id: str, execution_id: str, user_id: Optional[str] = None):
        """Log session execution start."""
        self.logger.info("Session execution started", extra={
            'event_type': 'session_started',
            'session_id': session_id,
            'execution_id': execution_id,
            'user_id': user_id
        })

    def log_session_completed(self, session_id: str, execution_id: str, 
                             files_transferred: int, bytes_transferred: int,
                             duration_seconds: float, user_id: Optional[str] = None):
        """Log session execution completion."""
        self.logger.info("Session execution completed", extra={
            'event_type': 'session_completed',
            'session_id': session_id,
            'execution_id': execution_id,
            'files_transferred': files_transferred,
            'bytes_transferred': bytes_transferred,
            'duration_seconds': duration_seconds,
            'user_id': user_id
        })

    def log_session_failed(self, session_id: str, execution_id: str, 
                          error: str, user_id: Optional[str] = None):
        """Log session execution failure."""
        self.logger.error("Session execution failed", extra={
            'event_type': 'session_failed',
            'session_id': session_id,
            'execution_id': execution_id,
            'error': error,
            'user_id': user_id
        })

    def log_file_operation(self, operation_type: str, source_path: str, 
                          dest_path: str, file_size: int, success: bool,
                          execution_id: Optional[str] = None):
        """Log individual file operation."""
        level = logging.INFO if success else logging.ERROR
        self.logger.log(level, f"File operation {operation_type}", extra={
            'event_type': 'file_operation',
            'operation_type': operation_type,
            'source_path': source_path,
            'dest_path': dest_path,
            'file_size': file_size,
            'success': success,
            'execution_id': execution_id
        })

    def log_authentication(self, user_id: str, success: bool, ip_address: Optional[str] = None):
        """Log authentication attempt."""
        level = logging.INFO if success else logging.WARNING
        event = "authentication_success" if success else "authentication_failure"
        
        self.logger.log(level, f"Authentication {event}", extra={
            'event_type': event,
            'user_id': user_id,
            'ip_address': ip_address
        })

    def log_configuration_change(self, setting_name: str, old_value: Any, 
                                new_value: Any, user_id: Optional[str] = None):
        """Log configuration change."""
        self.logger.info("Configuration changed", extra={
            'event_type': 'configuration_change',
            'setting_name': setting_name,
            'old_value': str(old_value),
            'new_value': str(new_value),
            'user_id': user_id
        })


class PerformanceLogger:
    """Logger for performance metrics."""

    def __init__(self):
        """Initialize performance logger."""
        self.logger = logging.getLogger('performance')

    def log_request_performance(self, method: str, path: str, duration_ms: float,
                               status_code: int, user_id: Optional[str] = None):
        """Log API request performance."""
        self.logger.info("API request completed", extra={
            'event_type': 'api_request',
            'method': method,
            'path': path,
            'duration_ms': duration_ms,
            'status_code': status_code,
            'user_id': user_id
        })

    def log_database_query_performance(self, query_type: str, table: str, 
                                     duration_ms: float, rows_affected: int = 0):
        """Log database query performance."""
        self.logger.debug("Database query completed", extra={
            'event_type': 'database_query',
            'query_type': query_type,
            'table': table,
            'duration_ms': duration_ms,
            'rows_affected': rows_affected
        })

    def log_file_transfer_performance(self, operation: str, file_size: int,
                                    duration_seconds: float, throughput_mbps: float):
        """Log file transfer performance."""
        self.logger.info("File transfer completed", extra={
            'event_type': 'file_transfer',
            'operation': operation,
            'file_size_bytes': file_size,
            'duration_seconds': duration_seconds,
            'throughput_mbps': throughput_mbps
        })

    def log_sync_performance(self, session_id: str, execution_id: str,
                           files_scanned: int, files_transferred: int,
                           total_bytes: int, duration_seconds: float):
        """Log sync operation performance."""
        throughput_mbps = (total_bytes / (1024 * 1024)) / duration_seconds if duration_seconds > 0 else 0
        
        self.logger.info("Sync operation completed", extra={
            'event_type': 'sync_performance',
            'session_id': session_id,
            'execution_id': execution_id,
            'files_scanned': files_scanned,
            'files_transferred': files_transferred,
            'total_bytes': total_bytes,
            'duration_seconds': duration_seconds,
            'throughput_mbps': round(throughput_mbps, 2)
        })


# Global instances
logging_manager = LoggingManager()
audit_logger = AuditLogger()
performance_logger = PerformanceLogger()


def get_logger(name: str) -> logging.Logger:
    """
    Get configured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger
    """
    return logging_manager.get_logger(name)


def configure_logging():
    """Configure application logging."""
    logging_manager.configure_logging()


def set_logging_context(**kwargs):
    """Set logging context for current thread."""
    logging_manager.set_context(**kwargs)


def clear_logging_context():
    """Clear logging context for current thread."""
    logging_manager.clear_context()
