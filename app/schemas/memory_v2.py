from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class MemoryClass(str, Enum):
    profile = "profile"
    preference = "preference"
    project = "project"
    task = "task"
    decision = "decision"
    repo = "repo"
    research = "research"
    knowledge = "knowledge"
    wiki = "wiki"
    finance = "finance"
    security = "security"
    ephemeral = "ephemeral"


class RetentionClass(str, Enum):
    persistent = "persistent"
    session = "session"
    ephemeral = "ephemeral"
    ttl = "ttl"


class ReviewStatus(str, Enum):
    candidate = "candidate"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class OriginType(str, Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"
    repo_watch = "repo_watch"
    web_ingest = "web_ingest"
    nostr_ingest = "nostr_ingest"
    import_job = "import"
    manual_review = "manual_review"


class MemoryScope(str, Enum):
    workspace = "workspace"
    pack = "pack"
    global_scope = "global"


class MemoryProvenance(BaseModel):
    origin_type: OriginType = OriginType.assistant
    source_label: Optional[str] = None
    source_uri: Optional[str] = None
    repo_name: Optional[str] = None
    repo_ref: Optional[str] = None
    commit_sha: Optional[str] = None
    issue_number: Optional[int] = None
    event_id: Optional[str] = None
    collected_at: Optional[datetime] = None
    extracted_by: Optional[str] = None
    extraction_note: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ReviewMetadata(BaseModel):
    status: ReviewStatus = ReviewStatus.candidate
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reason: Optional[str] = None
    supersedes_memory_id: Optional[str] = None
    canonical: bool = False
    pinned: bool = False


class MemoryCreateV2(BaseModel):
    workspace_id: str
    memory_class: MemoryClass
    key: str
    value: str
    summary: Optional[str] = None
    trust_level: str = "MEDIUM"
    retention_class: RetentionClass = RetentionClass.persistent
    provenance: MemoryProvenance = Field(default_factory=MemoryProvenance)
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)
    is_secret: bool = False
    created_by: str = "system"
    session_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    scope: MemoryScope = MemoryScope.workspace
    pack_name: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    content_type: str = Field("text", description="text, json, markdown, base64")
    ttl_seconds: Optional[int] = Field(
        None,
        ge=60,
        le=31_536_000,
        description="Required when retention_class=ttl.",
    )

    @model_validator(mode="after")
    def validate_model(self) -> "MemoryCreateV2":
        if self.is_secret:
            raise ValueError("Secrets must never enter Grokenstein memory.")
        if self.scope == MemoryScope.pack and not self.pack_name:
            raise ValueError("pack_name is required when scope='pack'.")
        if self.retention_class == RetentionClass.ttl and not self.ttl_seconds:
            raise ValueError("ttl_seconds is required when retention_class='ttl'.")
        if self.retention_class != RetentionClass.ttl and self.ttl_seconds is not None:
            raise ValueError("ttl_seconds is only valid when retention_class='ttl'.")
        if self.review.status == ReviewStatus.approved and not self.summary:
            raise ValueError("Approved memory should carry a concise summary.")
        return self


class MemoryReadV2(BaseModel):
    id: str
    workspace_id: str
    memory_class: MemoryClass
    key: str
    value: str
    summary: Optional[str]
    trust_level: str
    retention_class: RetentionClass
    provenance: MemoryProvenance
    review: ReviewMetadata
    is_secret: bool
    created_at: datetime
    updated_at: datetime
    created_by: str
    session_id: Optional[str]
    tags: List[str] = Field(default_factory=list)
    scope: MemoryScope = MemoryScope.workspace
    pack_name: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    timestamp: Optional[datetime] = None
    content_type: str = "text"
    ttl_seconds: Optional[int] = None
    model_config = {"from_attributes": True}


class MemorySearchV2(BaseModel):
    workspace_id: str
    query: str
    memory_class: Optional[MemoryClass] = None
    review_status: Optional[ReviewStatus] = None
    pack_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    limit: int = Field(10, ge=1, le=100)
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    include_archived: bool = False


class MemorySearchResultV2(BaseModel):
    record: MemoryReadV2
    score: float


class MemoryReviewAction(str, Enum):
    approve = "approve"
    reject = "reject"
    archive = "archive"
    pin = "pin"
    unpin = "unpin"
    mark_canonical = "mark_canonical"


class MemoryReviewRequest(BaseModel):
    workspace_id: str
    memory_id: str
    action: MemoryReviewAction
    reviewed_by: str
    reason: Optional[str] = None
    supersedes_memory_id: Optional[str] = None


class MemoryPromoteRequest(BaseModel):
    workspace_id: str
    source_memory_id: str
    new_key: Optional[str] = None
    new_summary: Optional[str] = None
    pack_name: Optional[str] = None
    reviewed_by: str
    reason: str = ""


class MemoryCandidatePolicy(BaseModel):
    auto_candidate_for_sources: List[OriginType] = Field(
        default_factory=lambda: [
            OriginType.assistant,
            OriginType.tool,
            OriginType.repo_watch,
            OriginType.web_ingest,
            OriginType.nostr_ingest,
        ]
    )
    auto_approve_for_sources: List[OriginType] = Field(
        default_factory=lambda: [OriginType.user, OriginType.manual_review]
    )
    require_summary_for_approval: bool = True
    require_provenance_for_candidate: bool = True
