from typing import Literal

from pydantic import BaseModel, Field


DecisionHorizon = Literal[
    "90 days",
    "12 months",
    "3 years",
]


class ResearchRequest(BaseModel):
    question: str = Field(
        min_length=10,
        max_length=1000,
        description="The business decision that needs to be researched.",
    )
    context: str = Field(
        default="",
        max_length=500,
        description="Relevant company or industry context.",
    )
    horizon: DecisionHorizon = "90 days"


class ResearchPlan(BaseModel):
    decision_question: str
    context: str
    horizon: DecisionHorizon
    subquestions: list[str]
    success_criteria: list[str]


class ResearchResponse(BaseModel):
    status: Literal["completed"]
    stage: Literal["planning"]
    plan: ResearchPlan