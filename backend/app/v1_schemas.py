from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class UserView(BaseModel):
    id: str
    username: str
    display_name: str
    roles: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserView


class AnalysisJobView(BaseModel):
    id: str
    owner_id: str
    source: str
    media_id: str | None
    file_name: str
    media_type: str
    status: str
    progress: int
    result_json: dict | None
    error_message: str | None
    site_id: str | None
    camera_code: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FieldReportCreate(BaseModel):
    analysis_job_id: str | None = None
    species_id: str | None = None
    species_name: str = "待确认物种"
    observed_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy: float | None = None
    location_text: str = ""
    notes: str = ""

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float | None) -> float | None:
        if value is not None and not -90 <= value <= 90:
            raise ValueError("纬度必须在 -90 到 90 之间")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float | None) -> float | None:
        if value is not None and not -180 <= value <= 180:
            raise ValueError("经度必须在 -180 到 180 之间")
        return value


class FieldReportView(BaseModel):
    id: str
    reporter_id: str
    analysis_job_id: str | None
    species_id: str | None
    species_name: str
    observed_at: datetime
    latitude: float | None
    longitude: float | None
    location_accuracy: float | None
    location_text: str
    notes: str
    status: str
    final_species_name: str | None
    review_comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewTaskView(BaseModel):
    id: str
    report_id: str | None
    analysis_job_id: str | None
    reason: str
    status: str
    reviewer_id: str | None
    decision: str | None
    corrected_species_name: str | None
    comment: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecisionRequest(BaseModel):
    version: int
    decision: str = Field(pattern="^(confirmed|corrected|rejected)$")
    corrected_species_name: str | None = None
    comment: str = ""
    promote_to_sample: bool = False


class ModelVersionCreate(BaseModel):
    pipeline: str
    version: str
    taxon_group: str = "animal"
    threshold: float = Field(default=0.65, ge=0, le=1)
    class_names: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)
    release_notes: str = ""


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    roles: list[str]


class UserStatusUpdate(BaseModel):
    is_active: bool
