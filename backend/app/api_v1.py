from __future__ import annotations

import csv
import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.auth import (
    audit,
    create_token,
    get_current_user,
    get_refresh_user,
    hash_password,
    require_roles,
    verify_password,
)
from app.database import SessionLocal, get_db
from app.domain_models import AnalysisJob, AuditLog, FieldReport, ModelVersion, ReviewTask, SpeciesResource, TrainingSample, User
from app.schemas import SpeciesCatalogResponse, SpeciesEntry
from app.services.species_catalog_service import get_species_catalog_service
from app.settings import get_settings
from app.v1_schemas import (
    AnalysisJobView,
    FieldReportCreate,
    FieldReportView,
    LoginRequest,
    ModelVersionCreate,
    ReviewDecisionRequest,
    ReviewTaskView,
    TokenResponse,
    UserCreate,
    UserStatusUpdate,
    UserView,
)

router = APIRouter(prefix="/api/v1")
admin_roles = ("reviewer", "data_operator", "system_admin")
manage_roles = ("data_operator", "system_admin")
allowed_media_extensions = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".avi"}


def _refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "wildlife_refresh",
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == request.username))
    if user is None or not user.is_active or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    audit(db, user, "auth.login", "user", user.id)
    db.commit()
    _refresh_cookie(response, create_token(user, "refresh"))
    return TokenResponse(access_token=create_token(user, "access"), user=UserView.model_validate(user))


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(response: Response, user: User = Depends(get_refresh_user)) -> TokenResponse:
    _refresh_cookie(response, create_token(user, "refresh"))
    return TokenResponse(access_token=create_token(user, "access"), user=UserView.model_validate(user))


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("wildlife_refresh", path="/api/v1/auth")
    return {"ok": True}


@router.get("/auth/me", response_model=UserView)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/features")
def features(user: User = Depends(get_current_user)) -> dict[str, bool]:
    return {"plant_recognition": get_settings().plant_recognition_enabled, "batch_zip_upload": True}


def _input_dir() -> Path:
    path = get_settings().storage_dir / "job-inputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _save_upload(upload: UploadFile) -> tuple[Path, str]:
    suffix = Path(upload.filename or "upload").suffix.lower()
    if suffix not in allowed_media_extensions:
        raise HTTPException(status_code=415, detail=f"不支持的素材类型：{suffix or '未知'}")
    target = _input_dir() / f"{uuid4()}{suffix}"
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            output.write(chunk)
    if get_settings().object_storage_enabled:
        from app.services.object_storage_service import get_object_storage_service

        get_object_storage_service().put_file(f"uploads/{target.name}", target, upload.content_type or "application/octet-stream")
    return target, upload.filename or target.name


async def _run_analysis_job(job_id: str, file_path: str, confidence: float, include_low_confidence: bool) -> None:
    from app.main import inference_service

    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.progress = 10
        db.commit()
    try:
        path = Path(file_path)
        with path.open("rb") as handle:
            upload = StarletteUploadFile(file=handle, filename=job.file_name)
            if job.media_type == "video":
                result = await inference_service.analyze_video(upload, confidence, 1.0, include_low_confidence)
            else:
                result = await inference_service.analyze_image(upload, confidence, include_low_confidence)
        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            if job is None:
                return
            job.media_id = result.media_id
            job.result_json = result.model_dump(mode="json")
            job.status = "succeeded"
            job.progress = 100
            review_reasons = sorted({reason for detection in result.detections for reason in detection.review_reasons})
            protected = any(
                candidate.protection_level and candidate.protection_level not in {"未收录", "暂无", "无"}
                for detection in result.detections
                for candidate in detection.top_candidates
            )
            needs_review = protected or any(detection.review_status != "ready" for detection in result.detections)
            if needs_review:
                db.add(ReviewTask(analysis_job_id=job.id, reason="；".join(review_reasons) or ("重点物种" if protected else "规则自动入队")))
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                db.commit()


def _dispatch_analysis(background_tasks: BackgroundTasks, job_id: str, file_path: str, confidence: float, include_low_confidence: bool) -> None:
    if get_settings().task_backend == "celery":
        from app.tasks import run_analysis_job

        run_analysis_job.delay(job_id, file_path, confidence, include_low_confidence)
    else:
        background_tasks.add_task(_run_analysis_job, job_id, file_path, confidence, include_low_confidence)


def _create_job(db: Session, user: User, file_path: Path, original_name: str, source: str, site_id: str | None, camera_code: str | None) -> AnalysisJob:
    media_type = "video" if file_path.suffix.lower() in {".mp4", ".mov", ".avi"} else "image"
    job = AnalysisJob(owner_id=user.id, source=source, file_name=original_name, media_type=media_type, site_id=site_id, camera_code=camera_code)
    db.add(job)
    db.flush()
    audit(db, user, "analysis.create", "analysis_job", job.id, source=source, file_name=original_name)
    return job


@router.post("/analysis-jobs", response_model=AnalysisJobView, status_code=202)
async def create_analysis_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    confidence_threshold: float = Form(0.35),
    include_low_confidence: bool = Form(False),
    site_id: str | None = Form(None),
    camera_code: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisJob:
    path, name = await _save_upload(file)
    job = _create_job(db, user, path, name, "mobile", site_id, camera_code)
    db.commit()
    _dispatch_analysis(background_tasks, job.id, str(path), confidence_threshold, include_low_confidence)
    return job


@router.post("/uploads/batch", response_model=list[AnalysisJobView], status_code=202)
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    site_id: str | None = Form(None),
    camera_code: str | None = Form(None),
    user: User = Depends(require_roles(*manage_roles)),
    db: Session = Depends(get_db),
) -> list[AnalysisJob]:
    if len(files) > 500:
        raise HTTPException(status_code=413, detail="单批次最多 500 个文件")
    saved: list[tuple[Path, str]] = []
    for upload in files:
        if Path(upload.filename or "").suffix.lower() == ".zip":
            archive_path = _input_dir() / f"{uuid4()}.zip"
            with archive_path.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    output.write(chunk)
            with zipfile.ZipFile(archive_path) as archive:
                members = [item for item in archive.infolist() if not item.is_dir()]
                if len(members) + len(saved) > 500 or sum(item.file_size for item in members) > 2 * 1024**3:
                    raise HTTPException(status_code=413, detail="压缩包文件数量或解压大小超限")
                for item in members:
                    source = Path(item.filename)
                    if source.is_absolute() or ".." in source.parts or source.suffix.lower() not in allowed_media_extensions:
                        raise HTTPException(status_code=400, detail=f"压缩包包含非法路径或文件类型：{item.filename}")
                    target = _input_dir() / f"{uuid4()}{source.suffix.lower()}"
                    with archive.open(item) as input_file, target.open("wb") as output:
                        shutil.copyfileobj(input_file, output)
                    saved.append((target, source.name))
            archive_path.unlink(missing_ok=True)
        else:
            saved.append(await _save_upload(upload))
    jobs: list[AnalysisJob] = []
    for path, name in saved:
        job = _create_job(db, user, path, name, "admin_batch", site_id, camera_code)
        jobs.append(job)
    db.commit()
    for job, (path, _) in zip(jobs, saved, strict=True):
        _dispatch_analysis(background_tasks, job.id, str(path), 0.35, False)
    return jobs


@router.get("/analysis-jobs", response_model=list[AnalysisJobView])
def my_analysis_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AnalysisJob]:
    return list(db.scalars(select(AnalysisJob).where(AnalysisJob.owner_id == user.id).order_by(AnalysisJob.created_at.desc()).limit(100)))


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJobView)
def get_analysis_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if job is None or (job.owner_id != user.id and not set(user.roles).intersection(admin_roles)):
        raise HTTPException(status_code=404, detail="识别任务不存在")
    return job


@router.get("/species", response_model=SpeciesCatalogResponse)
def species_catalog(
    category: str | None = None,
    query: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeciesCatalogResponse:
    stored = list(db.scalars(select(SpeciesResource).order_by(SpeciesResource.species_id)))
    merged = {entry.species_id: entry for entry in get_species_catalog_service().list_species()}
    for item in stored:
        if item.is_deleted:
            merged.pop(item.species_id, None)
        else:
            merged[item.species_id] = SpeciesEntry.model_validate(item.payload)
    species = sorted(merged.values(), key=lambda entry: (entry.latin_name or entry.cn_name).casefold())
    if category:
        species = [entry for entry in species if entry.category == category]
    if query:
        needle = query.strip().lower()
        species = [entry for entry in species if needle in " ".join([entry.cn_name, entry.latin_name or "", entry.family or "", entry.genus or ""]).lower()]
    return SpeciesCatalogResponse(species_count=len(species), species=species)


@router.get("/species/{species_id}", response_model=SpeciesEntry)
def species_detail(species_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SpeciesEntry:
    stored = db.get(SpeciesResource, species_id)
    if stored and stored.is_deleted:
        raise HTTPException(status_code=404, detail="物种不存在")
    entry = SpeciesEntry.model_validate(stored.payload) if stored else get_species_catalog_service().get_species(species_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="物种不存在")
    return entry


@router.put("/admin/species/{species_id}", response_model=SpeciesEntry)
def save_species(payload: SpeciesEntry, species_id: str, user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> SpeciesEntry:
    if payload.species_id != species_id:
        raise HTTPException(status_code=422, detail="路径物种 ID 与数据不一致")
    resource = db.get(SpeciesResource, species_id)
    if resource is None:
        resource = SpeciesResource(species_id=species_id, payload=payload.model_dump(mode="json"))
        db.add(resource)
    else:
        resource.payload = payload.model_dump(mode="json")
        resource.is_deleted = False
    audit(db, user, "species.save", "species", species_id)
    db.commit()
    return payload


@router.post("/admin/species/import")
async def import_species(
    file: UploadFile = File(...),
    user: User = Depends(require_roles(*manage_roles)),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Import species resources from a CSV or JSON file."""
    filename = (file.filename or "").lower()
    raw = await file.read()
    try:
        if filename.endswith(".json") or (file.content_type or "").lower().endswith("json"):
            payload = json.loads(raw.decode("utf-8-sig"))
            rows = payload.get("species", []) if isinstance(payload, dict) else payload
        elif filename.endswith(".csv") or (file.content_type or "").lower().endswith("csv"):
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        else:
            raise HTTPException(status_code=415, detail="仅支持 CSV 或 JSON 文件")
    except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as exc:
        raise HTTPException(status_code=422, detail=f"资源文件格式无效：{exc}") from exc
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=422, detail="资源文件中没有可导入的物种记录")

    created = 0
    updated = 0
    for row in rows:
        if not isinstance(row, dict):
            raise HTTPException(status_code=422, detail="每条物种记录必须是对象")
        try:
            entry = SpeciesEntry.model_validate(row)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"物种字段校验失败：{exc}") from exc
        resource = db.get(SpeciesResource, entry.species_id)
        if resource is None:
            db.add(SpeciesResource(species_id=entry.species_id, payload=entry.model_dump(mode="json")))
            created += 1
        else:
            resource.payload = entry.model_dump(mode="json")
            resource.is_deleted = False
            updated += 1
        audit(db, user, "species.import", "species", entry.species_id)
    db.commit()
    return {"created": created, "updated": updated, "total": created + updated}


@router.get("/admin/species/import-template")
def download_species_import_template(user: User = Depends(require_roles(*manage_roles))) -> Response:
    """Download a valid one-row JSON template for the species importer."""
    example = SpeciesEntry(
        species_id="example_species",
        cn_name="示例物种",
        latin_name="Genus species",
        category="animal",
        taxon_group="兽类",
        order="示例目",
        family="示例科",
        genus="示例属",
        protection_level="未列入重点保护名录",
        source_scope="资料来源说明",
        recognition_tier="candidate",
        habits="活动习性说明",
        diet="食性说明",
        features=["识别特征一", "识别特征二"],
        habitat="生境说明",
        monitoring_value="监测价值说明",
        similar_species=["相似物种名称"],
        review_tips="人工复核提示",
        tags=["示例标签"],
    )
    content = json.dumps({"species": [example.model_dump(mode="json")]}, ensure_ascii=False, indent=2) + "\n"
    return Response(
        content="\ufeff" + content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="species-import-template.json"'},
    )


@router.delete("/admin/species/{species_id}")
def delete_species(species_id: str, user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> dict[str, bool]:
    resource = db.get(SpeciesResource, species_id)
    if resource is None:
        current = get_species_catalog_service().get_species(species_id)
        if current is None:
            raise HTTPException(status_code=404, detail="物种不存在")
        resource = SpeciesResource(species_id=species_id, payload=current.model_dump(mode="json"), is_deleted=True)
        db.add(resource)
    else:
        resource.is_deleted = True
    audit(db, user, "species.delete", "species", species_id)
    db.commit()
    return {"deleted": True}


@router.post("/field-reports", response_model=FieldReportView, status_code=201)
def create_field_report(payload: FieldReportCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FieldReport:
    if payload.analysis_job_id:
        job = db.get(AnalysisJob, payload.analysis_job_id)
        if job is None or job.owner_id != user.id:
            raise HTTPException(status_code=404, detail="关联识别任务不存在")
    report = FieldReport(
        reporter_id=user.id,
        **payload.model_dump(exclude={"observed_at"}),
        observed_at=payload.observed_at or datetime.now(timezone.utc),
    )
    db.add(report)
    db.flush()
    db.add(ReviewTask(report_id=report.id, analysis_job_id=report.analysis_job_id, reason="移动端重点物种上报"))
    audit(db, user, "field_report.create", "field_report", report.id)
    db.commit()
    return report


@router.get("/field-reports", response_model=list[FieldReportView])
def my_field_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FieldReport]:
    return list(db.scalars(select(FieldReport).where(FieldReport.reporter_id == user.id).order_by(FieldReport.created_at.desc()).limit(100)))


@router.get("/admin/reviews", response_model=list[ReviewTaskView])
def list_reviews(review_status: str | None = None, user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> list[ReviewTask]:
    statement = select(ReviewTask).order_by(ReviewTask.created_at.desc())
    if review_status:
        statement = statement.where(ReviewTask.status == review_status)
    return list(db.scalars(statement.limit(200)))


@router.get("/admin/field-reports", response_model=list[FieldReportView])
def admin_field_reports(user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> list[FieldReport]:
    """Return mobile field reports for the admin review workspace."""
    return list(db.scalars(select(FieldReport).order_by(FieldReport.created_at.desc()).limit(500)))


@router.post("/admin/reviews/{task_id}/claim", response_model=ReviewTaskView)
def claim_review(task_id: str, user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> ReviewTask:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="复核任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail="该任务已被领取或处理")
    task.status = "claimed"
    task.reviewer_id = user.id
    task.version += 1
    audit(db, user, "review.claim", "review_task", task.id)
    db.commit()
    return task


@router.post("/admin/reviews/{task_id}/decision", response_model=ReviewTaskView)
def decide_review(payload: ReviewDecisionRequest, task_id: str, user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> ReviewTask:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="复核任务不存在")
    if task.version != payload.version:
        raise HTTPException(status_code=409, detail="任务已被其他专家更新，请刷新后重试")
    if task.reviewer_id not in {None, user.id} and "system_admin" not in user.roles:
        raise HTTPException(status_code=409, detail="该任务已由其他专家领取")
    task.status = "resolved"
    task.reviewer_id = user.id
    task.decision = payload.decision
    task.corrected_species_name = payload.corrected_species_name
    task.comment = payload.comment
    task.version += 1
    if task.report_id:
        report = db.get(FieldReport, task.report_id)
        if report:
            report.status = "resolved"
            report.final_species_name = payload.corrected_species_name or report.species_name
            report.review_comment = payload.comment
    if payload.promote_to_sample and task.analysis_job_id:
        job = db.get(AnalysisJob, task.analysis_job_id)
        if job and job.media_id:
            db.add(TrainingSample(media_id=job.media_id, species_name=payload.corrected_species_name or "已确认物种", status="confirmed"))
    audit(db, user, "review.decision", "review_task", task.id, decision=payload.decision)
    db.commit()
    return task


@router.get("/admin/media", response_model=list[AnalysisJobView])
def admin_media(job_status: str | None = None, user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> list[AnalysisJob]:
    statement = select(AnalysisJob).order_by(AnalysisJob.created_at.desc())
    if job_status:
        statement = statement.where(AnalysisJob.status == job_status)
    return list(db.scalars(statement.limit(500)))


@router.get("/admin/media/export.csv")
def export_media(user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = list(db.scalars(select(AnalysisJob).order_by(AnalysisJob.created_at.desc())))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["任务ID", "文件名", "来源", "状态", "媒体ID", "创建时间"])
    writer.writerows([[row.id, row.file_name, row.source, row.status, row.media_id or "", row.created_at.isoformat()] for row in rows])
    audit(db, user, "media.export", "analysis_job", None, count=len(rows))
    db.commit()
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=monitoring-data.csv"})


def _csv_response(filename: str, output: io.StringIO) -> StreamingResponse:
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _detections(job: AnalysisJob) -> list[dict]:
    if not isinstance(job.result_json, dict):
        return []
    detections = job.result_json.get("detections")
    return detections if isinstance(detections, list) else []


def _detection_species(detection: dict) -> str:
    label = detection.get("species_label") or detection.get("label") or "待确认物种"
    return str(label)


def _detection_confidence(detection: dict) -> float:
    value = detection.get("confidence", detection.get("classification_confidence", 0))
    return float(value or 0)


@router.get("/admin/reports/overview")
def reports_overview(user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> dict[str, object]:
    jobs = list(db.scalars(select(AnalysisJob)))
    reports = list(db.scalars(select(FieldReport)))
    reviews = list(db.scalars(select(ReviewTask)))
    detections = [detection for job in jobs for detection in _detections(job)]
    species_names = {_detection_species(detection) for detection in detections}
    species_names.update((report.final_species_name or report.species_name) for report in reports if report.status == "resolved")
    months = {job.created_at.strftime("%Y-%m") for job in jobs}
    months.update(report.observed_at.strftime("%Y-%m") for report in reports)
    return {
        "patrol": {
            "media_count": len(jobs),
            "succeeded_count": sum(1 for job in jobs if job.status == "succeeded"),
            "pending_review_count": sum(1 for review in reviews if review.status == "pending"),
        },
        "species": {
            "species_count": len([name for name in species_names if name and name != "待确认物种"]),
            "detection_count": len(detections) + len([report for report in reports if report.status == "resolved"]),
            "reviewed_report_count": sum(1 for report in reports if report.status == "resolved"),
        },
        "annual": {
            "month_count": len(months),
            "media_count": len(jobs),
            "resolved_review_count": sum(1 for review in reviews if review.status == "resolved"),
        },
    }


@router.get("/admin/reports/patrol.csv")
def export_patrol_report(user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> StreamingResponse:
    jobs = list(db.scalars(select(AnalysisJob).order_by(AnalysisJob.created_at.desc())))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["任务ID", "文件名", "来源", "监测点", "相机编号", "素材类型", "状态", "检出目标数", "创建时间"])
    writer.writerows([
        [job.id, job.file_name, job.source, job.site_id or "", job.camera_code or "", job.media_type, job.status, len(_detections(job)), job.created_at.isoformat()]
        for job in jobs
    ])
    audit(db, user, "report.export", "patrol_report", None, count=len(jobs))
    db.commit()
    return _csv_response("patrol-report.csv", output)


@router.get("/admin/reports/species.csv")
def export_species_report(user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> StreamingResponse:
    jobs = list(db.scalars(select(AnalysisJob).where(AnalysisJob.status == "succeeded").order_by(AnalysisJob.created_at.desc())))
    reports = list(db.scalars(select(FieldReport).where(FieldReport.status == "resolved").order_by(FieldReport.observed_at.desc())))
    species: dict[str, dict[str, object]] = {}
    for job in jobs:
        for detection in _detections(job):
            name = _detection_species(detection)
            entry = species.setdefault(name, {"count": 0, "confidence": 0.0, "last_seen": job.created_at, "source": "模型识别"})
            entry["count"] = int(entry["count"]) + 1
            entry["confidence"] = max(float(entry["confidence"]), _detection_confidence(detection))
            if job.created_at > entry["last_seen"]:
                entry["last_seen"] = job.created_at
    for report in reports:
        name = report.final_species_name or report.species_name
        entry = species.setdefault(name, {"count": 0, "confidence": 0.0, "last_seen": report.observed_at, "source": "人工上报"})
        entry["count"] = int(entry["count"]) + 1
        if report.observed_at > entry["last_seen"]:
            entry["last_seen"] = report.observed_at
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["物种名称", "发现次数", "最高置信度", "最近发现时间", "来源"])
    for name, entry in sorted(species.items(), key=lambda item: (-int(item[1]["count"]), item[0])):
        writer.writerow([name, entry["count"], f"{float(entry['confidence']):.4f}", entry["last_seen"].isoformat(), entry["source"]])
    audit(db, user, "report.export", "species_report", None, count=len(species))
    db.commit()
    return _csv_response("species-discovery-report.csv", output)


@router.get("/admin/reports/annual.csv")
def export_annual_report(user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> StreamingResponse:
    jobs = list(db.scalars(select(AnalysisJob)))
    reports = list(db.scalars(select(FieldReport)))
    reviews = list(db.scalars(select(ReviewTask)))
    months: dict[str, dict[str, int]] = {}
    for job in jobs:
        entry = months.setdefault(job.created_at.strftime("%Y-%m"), {"media": 0, "detections": 0, "field_reports": 0, "reviews": 0})
        entry["media"] += 1
        entry["detections"] += len(_detections(job))
    for report in reports:
        months.setdefault(report.observed_at.strftime("%Y-%m"), {"media": 0, "detections": 0, "field_reports": 0, "reviews": 0})["field_reports"] += 1
    for review in reviews:
        if review.status == "resolved":
            months.setdefault(review.updated_at.strftime("%Y-%m"), {"media": 0, "detections": 0, "field_reports": 0, "reviews": 0})["reviews"] += 1
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["月份", "素材数量", "检出目标数", "重点物种上报", "已完成复核"])
    for month in sorted(months, reverse=True):
        entry = months[month]
        writer.writerow([month, entry["media"], entry["detections"], entry["field_reports"], entry["reviews"]])
    audit(db, user, "report.export", "annual_report", None, count=len(months))
    db.commit()
    return _csv_response("annual-monitoring-report.csv", output)


@router.get("/admin/analytics/overview")
def analytics_overview(user: User = Depends(require_roles(*admin_roles)), db: Session = Depends(get_db)) -> dict[str, object]:
    return {
        "media_count": db.scalar(select(func.count()).select_from(AnalysisJob)) or 0,
        "detection_count": sum(len(row.result_json.get("detections", [])) for row in db.scalars(select(AnalysisJob).where(AnalysisJob.result_json.is_not(None))) if row.result_json),
        "priority_species_count": db.scalar(select(func.count()).select_from(FieldReport)) or 0,
        "pending_review_count": db.scalar(select(func.count()).select_from(ReviewTask).where(ReviewTask.status == "pending")) or 0,
        "plant_recognition_enabled": get_settings().plant_recognition_enabled,
    }


@router.get("/admin/samples")
def list_samples(user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "media_id": row.media_id, "species_name": row.species_name, "status": row.status, "source": row.source} for row in db.scalars(select(TrainingSample).order_by(TrainingSample.created_at.desc()).limit(500))]


@router.get("/admin/models")
def list_models(user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "pipeline": row.pipeline, "version": row.version, "taxon_group": row.taxon_group, "threshold": row.threshold, "metrics": row.metrics, "is_active": row.is_active} for row in db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc()))]


@router.post("/admin/models", status_code=201)
def create_model(payload: ModelVersionCreate, user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> dict:
    model = ModelVersion(**payload.model_dump())
    db.add(model)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="该管线版本已存在") from exc
    audit(db, user, "model.create", "model_version", model.id)
    db.commit()
    return {"id": model.id, "pipeline": model.pipeline, "version": model.version, "is_active": model.is_active}


@router.post("/admin/models/{model_id}/activate")
def activate_model(model_id: str, user: User = Depends(require_roles(*manage_roles)), db: Session = Depends(get_db)) -> dict:
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="模型版本不存在")
    for active in db.scalars(select(ModelVersion).where(ModelVersion.pipeline == model.pipeline, ModelVersion.is_active.is_(True))):
        active.is_active = False
    model.is_active = True
    audit(db, user, "model.activate", "model_version", model.id, pipeline=model.pipeline, version=model.version)
    db.commit()
    return {"id": model.id, "is_active": True}


@router.get("/admin/users", response_model=list[UserView])
def list_users(user: User = Depends(require_roles("system_admin")), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.post("/admin/users", response_model=UserView, status_code=201)
def create_user(payload: UserCreate, user: User = Depends(require_roles("system_admin")), db: Session = Depends(get_db)) -> User:
    allowed_roles = {"patrol_user", "reviewer", "data_operator", "system_admin"}
    if not payload.roles or not set(payload.roles).issubset(allowed_roles):
        raise HTTPException(status_code=422, detail="角色配置无效")
    account = User(username=payload.username, display_name=payload.display_name, password_hash=hash_password(payload.password), roles=payload.roles)
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="用户名已存在") from exc
    audit(db, user, "user.create", "user", account.id, username=account.username, roles=account.roles)
    db.commit()
    return account


@router.patch("/admin/users/{user_id}/status", response_model=UserView)
def update_user_status(payload: UserStatusUpdate, user_id: str, user: User = Depends(require_roles("system_admin")), db: Session = Depends(get_db)) -> User:
    account = db.get(User, user_id)
    if account is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if account.id == user.id and not payload.is_active:
        raise HTTPException(status_code=409, detail="不能停用当前登录账号")
    account.is_active = payload.is_active
    audit(db, user, "user.status", "user", account.id, is_active=payload.is_active)
    db.commit()
    return account


@router.get("/admin/audit-logs")
def audit_logs(user: User = Depends(require_roles("system_admin")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": row.id, "actor_id": row.actor_id, "action": row.action, "target_type": row.target_type, "target_id": row.target_id, "details": row.details, "created_at": row.created_at} for row in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500))]


@router.post("/admin/backups", status_code=202)
def create_backup(user: User = Depends(require_roles("system_admin")), db: Session = Depends(get_db)) -> dict[str, str]:
    backup_dir = get_settings().storage_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_id = f"backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    manifest = backup_dir / f"{backup_id}.json"
    manifest.write_text(json.dumps({"id": backup_id, "created_at": datetime.now(timezone.utc).isoformat(), "created_by": user.id, "database_url_redacted": True}, ensure_ascii=False, indent=2), encoding="utf-8")
    audit(db, user, "backup.create", "backup", backup_id)
    db.commit()
    return {"id": backup_id, "status": "manifest_created"}
