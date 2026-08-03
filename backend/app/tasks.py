import asyncio

from app.celery_app import celery_app


@celery_app.task(name="analysis.run", autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def run_analysis_job(job_id: str, file_path: str, confidence: float, include_low_confidence: bool) -> None:
    from app.api_v1 import _run_analysis_job

    asyncio.run(_run_analysis_job(job_id, file_path, confidence, include_low_confidence))
