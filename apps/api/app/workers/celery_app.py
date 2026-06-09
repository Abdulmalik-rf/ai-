"""Celery application.

Three queues:
  - default     — small everyday work (audit log batch flushes, billing housekeeping)
  - ingestion   — heavy I/O + embeddings (per-document)
  - llm         — long-running LLM calls (contract review, case analysis async)

Beat schedule runs business-readiness sweeps daily:
  - trial-expiry & dunning: surfaces past-due tenants, sends reminder emails
  - purge: hard-scrubs accounts/tenants past their PDPL grace window
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "legalai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks", "app.workers.lifecycle"],
)

celery_app.conf.update(
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.ingest_document_task": {"queue": "ingestion"},
        "app.workers.tasks.contract_review_task": {"queue": "llm"},
        "app.workers.tasks.case_analysis_task": {"queue": "llm"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=20 * 60,
    task_soft_time_limit=18 * 60,
    timezone="Asia/Riyadh",
    beat_schedule={
        "trial-expiry-and-dunning": {
            "task": "app.workers.lifecycle.run_billing_lifecycle_sweep",
            "schedule": crontab(hour=2, minute=15),  # daily at 02:15 KSA
        },
        "purge-deleted-accounts": {
            "task": "app.workers.lifecycle.run_pdpl_purge_sweep",
            "schedule": crontab(hour=3, minute=0),  # daily at 03:00 KSA
        },
        # Sweep open tasks every 15 minutes during working hours (07:00–21:00
        # KSA). The query is cheap (single index hit on `due_date <= today`
        # AND `due_reminder_sent_at IS NULL`) so we run frequently rather
        # than once a day — that way a task due at 14:00 doesn't wait until
        # tomorrow morning to ping the assignee.
        "task-due-reminders": {
            "task": "app.workers.lifecycle.run_task_reminder_sweep",
            "schedule": crontab(minute="*/15", hour="7-21"),
        },
    },
)
