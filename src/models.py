from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionHorizon = Literal[
    "90 days",
    "12 months",
    "3 years",
]

EvidenceLevel = Literal[
    "high",
    "medium",
    "low",
]

SourceType = Literal[
    "government",
    "academic",
    "industry_report",
    "company",
    "news",
    "other",
]


class ResearchRequest(BaseModel):
    question: str = Field(
        min_length=10,
        max_length=1000,
        description=(
            "需要研究的商业决策问题。"
        ),
    )
    context: str = Field(
        default="",
        max_length=500,
        description="与决策相关的企业或行业背景。",
    )
    horizon: DecisionHorizon = "90 days"


class ResearchPlan(BaseModel):
    decision_question: str
    context: str
    horizon: str
    subquestions: list[str]
    search_queries: list[str]
    success_criteria: list[str]


class EvidenceRecord(BaseModel):
    title: str
    url: str
    excerpt: str
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    query: str


class EvidenceBundle(BaseModel):
    query: str
    records: list[EvidenceRecord]


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: SourceType
    quality: EvidenceLevel
    relevance: EvidenceLevel
    key_claim: str
    limitations: str


class CitedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    source_ids: list[str]


class DecisionBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    recommendation: str
    confidence: EvidenceLevel
    key_findings: list[CitedFinding]
    alternatives: list[str]
    risks: list[str]
    next_steps: list[str]


class ResearchResponse(BaseModel):
    status: Literal["completed"]
    stage: Literal[
        "planning",
        "research",
        "review",
        "decision",
    ]
    plan: ResearchPlan
    evidence: list[EvidenceBundle] = Field(
        default_factory=list,
    )
    assessments: list[EvidenceAssessment] = Field(
        default_factory=list,
    )
    brief: DecisionBrief | None = None
