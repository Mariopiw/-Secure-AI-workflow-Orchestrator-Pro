from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

celery_app = Celery(
    "secure_ai_workflow_orchestrator_pro",
    broker=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_ignore_result=True,
    broker_transport_options={"visibility_timeout": 3600},
    timezone="UTC",
)

celery_app.conf.beat_schedule = {
    "dispatch-outbox-every-10-seconds": {
        "task": "app.tasks.dispatch_outbox",
        "schedule": 10.0,
    },
    "recover-stuck-workflows-every-minute": {
        "task": "app.tasks.recover_stuck_workflows",
        "schedule": 60.0,
    },
}
