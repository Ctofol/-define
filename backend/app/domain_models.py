from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_string() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(32), default="mobile")
    media_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(20), default="image")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    camera_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(32))
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(60), default="upload")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)


class CameraSite(Base, TimestampMixin):
    __tablename__ = "camera_sites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    region: Mapped[str] = mapped_column(String(160), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)


class CameraDevice(Base, TimestampMixin):
    __tablename__ = "camera_devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    site_id: Mapped[str] = mapped_column(ForeignKey("camera_sites.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="active")


class FieldReport(Base, TimestampMixin):
    __tablename__ = "field_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    analysis_job_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=True)
    species_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    species_name: Mapped[str] = mapped_column(String(160), default="待确认物种")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_text: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="submitted", index=True)
    final_species_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewTask(Base, TimestampMixin):
    __tablename__ = "review_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("field_reports.id"), nullable=True, index=True)
    analysis_job_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    corrected_species_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("pipeline", "version", name="uq_model_pipeline_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    pipeline: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(80))
    taxon_group: Mapped[str] = mapped_column(String(80), default="animal")
    threshold: Mapped[float] = mapped_column(Float, default=0.65)
    class_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    release_notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class TrainingSample(Base, TimestampMixin):
    __tablename__ = "training_samples"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    media_id: Mapped[str] = mapped_column(String(120), index=True)
    species_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="pending_label", index=True)
    source: Mapped[str] = mapped_column(String(60), default="review")


class SpeciesResource(Base, TimestampMixin):
    __tablename__ = "species_resources"
    species_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ReportExport(Base, TimestampMixin):
    __tablename__ = "report_exports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    report_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MigrationRecord(Base):
    __tablename__ = "migration_records"
    __table_args__ = (UniqueConstraint("source_type", "source_key", name="uq_migration_source"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    source_type: Mapped[str] = mapped_column(String(80))
    source_key: Mapped[str] = mapped_column(String(255))
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="imported")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
