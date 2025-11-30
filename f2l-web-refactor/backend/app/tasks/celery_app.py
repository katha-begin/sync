"""
Celery application configuration for F2L Web Refactor.
"""
from celery import Celery
from celery.signals import worker_init, worker_shutdown
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "f2l_sync",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.sync_tasks",
        "app.tasks.health_tasks",
        "app.tasks.maintenance_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "app.tasks.sync_tasks.*": {"queue": "sync"},
        "app.tasks.health_tasks.*": {"queue": "health"},
        "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
    
    # Task execution
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task result settings
    result_expires=3600,  # 1 hour
    task_track_started=True,
    task_send_sent_event=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task time limits
    task_soft_time_limit=3600,  # 1 hour soft limit
    task_time_limit=3900,       # 65 minutes hard limit
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "health-check-endpoints": {
            "task": "app.tasks.health_tasks.check_all_endpoints_health",
            "schedule": 300.0,  # Every 5 minutes
        },
        "cleanup-old-executions": {
            "task": "app.tasks.maintenance_tasks.cleanup_old_executions",
            "schedule": 3600.0,  # Every hour
        },
        "process-scheduled-sessions": {
            "task": "app.tasks.sync_tasks.process_scheduled_sessions",
            "schedule": 60.0,  # Every minute
        },
    },
    beat_schedule_filename="celerybeat-schedule",
)


@worker_init.connect
def worker_init_handler(sender=None, conf=None, **kwargs):
    """Initialize worker."""
    logger.info(f"Celery worker {sender} initialized")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, conf=None, **kwargs):
    """Cleanup on worker shutdown."""
    logger.info(f"Celery worker {sender} shutting down")


# Task state constants
class TaskState:
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


# Custom task base class
class BaseTask(celery_app.Task):
    """Base task class with common functionality."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on task success."""
        logger.info(f"Task {task_id} completed successfully")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")


# Set default task base class
celery_app.Task = BaseTask


def get_celery_app():
    """Get Celery application instance."""
    return celery_app
