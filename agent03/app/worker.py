from celery import Celery

from app.config import get_settings
from app.database import Database, Job, Report
from app.providers import build_providers
from app.services.jobs import JobService
from app.services.reports import ReportService

settings = get_settings()
celery_app = Celery(
    "docflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
)


@celery_app.task(name="docflow.process_job", bind=True, max_retries=2)
def process_job(self, job_id: str):
    database = Database(settings.database_url)
    providers = build_providers(settings)
    with database.session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return {"status": "missing"}
        service = JobService(session, job.tenant_id, "system-worker", providers)
        try:
            result = service.run_fake(job_id)
            return {"status": result.status, "job_id": result.id}
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                raise
            raise self.retry(exc=exc, countdown=2 ** self.request.retries) from exc


@celery_app.task(name="docflow.generate_report", bind=True, max_retries=2)
def generate_report(self, report_id: str):
    database = Database(settings.database_url)
    providers = build_providers(settings)
    with database.session_factory() as session:
        report = session.get(Report, report_id)
        if report is None:
            return {"status": "missing"}
        service = ReportService(session, report.tenant_id, report.created_by, providers)
        try:
            result = service.generate(report_id)
            return {"status": result.status, "report_id": result.id}
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                raise
            raise self.retry(exc=exc, countdown=2 ** self.request.retries) from exc

