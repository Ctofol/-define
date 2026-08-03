from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class SpeciesCandidate(BaseModel):
    label: str
    confidence: float
    source: str = "classifier"
    evidence: str | None = None
    sample_url: str | None = None
    species_id: str | None = None
    latin_name: str | None = None
    taxon_group: str | None = None
    protection_level: str | None = None
    region_status: str = "unknown"
    priority: str = "unknown"
    review_flags: list[str] = Field(default_factory=list)


class DetectionResult(BaseModel):
    media_id: str
    frame_time: float = Field(description="Seconds from the start of the media.")
    bbox: BoundingBox
    detected_type: str
    species_label: str
    confidence: float
    detection_confidence: float = 0.0
    classification_confidence: float = 0.0
    retrieval_confidence: float = 0.0
    top_candidates: list[SpeciesCandidate] = Field(default_factory=list)
    review_status: str = "needs_review"
    review_reasons: list[str] = Field(default_factory=list)
    preview_crop_path: str


class AnalysisResponse(BaseModel):
    media_id: str
    media_type: str
    preview_url: str | None
    detections: list[DetectionResult]
    species_summary: dict[str, int]
    model_status: dict[str, str]
    message: str


class SpeciesEntry(BaseModel):
    species_id: str
    cn_name: str
    latin_name: str | None = None
    category: str
    taxon_group: str | None = None
    order: str | None = None
    family: str | None = None
    genus: str | None = None
    protection_level: str
    source_scope: str
    source_page: int | None = None
    recognition_tier: str
    habits: str = ""
    diet: str = ""
    features: list[str]
    habitat: str
    monitoring_value: str
    similar_species: list[str] = Field(default_factory=list)
    review_tips: str
    tags: list[str] = Field(default_factory=list)
    life_form: str = ""
    phenology: str = ""
    distribution: str = ""
    source_urls: list[str] = Field(default_factory=list)
    image_url: str | None = None
    image_source_url: str | None = None
    image_author: str = ""
    image_license: str = ""
    image_basis_of_record: str = ""
    rejected_image_sources: list[str] = Field(default_factory=list)


class ReferenceSampleEntry(BaseModel):
    file_name: str
    file_url: str
    source: str | None = None
    author: str | None = None
    license: str | None = None
    sex: str | None = None
    cn_name: str | None = None
    scientific_name: str | None = None
    category: str | None = None
    taxon_group: str | None = None
    protection_level: str | None = None
    source_pdf: str | None = None
    source_page: int | None = None
    match_status: str | None = None
    subspecies: str | None = None
    note: str | None = None


class ReferenceSpeciesEntry(BaseModel):
    folder_name: str
    image_count: int
    metadata_rows: int
    cover_url: str | None = None
    sample_urls: list[str] = Field(default_factory=list)
    samples: list[ReferenceSampleEntry] = Field(default_factory=list)


class ReferenceLibraryResponse(BaseModel):
    species: list[ReferenceSpeciesEntry]


class SpeciesCatalogResponse(BaseModel):
    species_count: int
    species: list[SpeciesEntry]


class AssistantMessage(BaseModel):
    role: str
    content: str


class AssistantChatRequest(BaseModel):
    question: str
    context_species_id: str | None = None
    messages: list[AssistantMessage] = Field(default_factory=list)


class AssistantSource(BaseModel):
    species_id: str
    cn_name: str
    latin_name: str | None = None
    protection_level: str
    matched_fields: list[str] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    answer: str
    mode: str = "local_knowledge"
    review_notice: str
    sources: list[AssistantSource] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
