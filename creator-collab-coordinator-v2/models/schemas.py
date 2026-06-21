from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime, timezone


class AgentSource(str, Enum):
    ADVISOR = "advisor"
    MATCH = "match"
    LEDGER = "ledger"
    SYSTEM = "system"


class Severity(str, Enum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class LedgerEntry(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: AgentSource
    event_type: str
    message: str
    data: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    severity: Severity = Severity.NORMAL


class SocialMetric(BaseModel):
    name: str
    value: str
    unit: str = ""
    flag: Severity = Severity.NORMAL
    reference_range: str = ""


class ExpertiseArea(BaseModel):
    skill_id: str
    category: str = "SKILL"
    description: str


class Deliverable(BaseModel):
    deliverable_id: str
    category: str = "POST"
    name: str
    brand_objective: str


class CreatorProfile(BaseModel):
    creator_name: str
    creator_follower_count: int
    creator_primary_platform: str
    creator_specialty: str
    focus_area: str = ""
    audience_demographics: list[str] = Field(default_factory=list)
    social_metrics: list[SocialMetric] = Field(default_factory=list)
    expertise_areas: list[ExpertiseArea] = Field(default_factory=list)
    proposed_deliverables: Optional[Deliverable] = None
    previous_collaborations: list[str] = Field(default_factory=list)
    bio: str = ""


class BrandRequirement(BaseModel):
    section_id: str
    title: str
    text: str
    relevance_score: float = 0.0
    is_flexible: bool = False


class BrandProfile(BaseModel):
    brand_name: str
    brand_id: str
    guidelines_document: str  # full text
    matched_requirements: list[BrandRequirement] = Field(default_factory=list)


class MatchResult(BaseModel):
    status: str  # MATCHED, DECLINED, PENDING_REVIEW
    match_pathway: str
    reasoning: str
    brand_requirements_cited: list[str]
    collaboration_timeline: str
    confidence_score: float
    expected_reach: str = ""


class CollaborationRequest(BaseModel):
    creator_profile: CreatorProfile
    brand_guidelines: str
    brand_name: str = "Sample Brand"
    brand_id: str = "DEMO-001"


class SSEEvent(BaseModel):
    event: str
    source: AgentSource
    message: str
    data: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    severity: Severity = Severity.NORMAL
