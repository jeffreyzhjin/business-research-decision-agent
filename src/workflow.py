import json
import os

from dotenv import load_dotenv
from groq import AsyncGroq
from pydantic import BaseModel, ConfigDict, Field

from .models import ResearchPlan, ResearchRequest, ResearchResponse


load_dotenv()

MODEL_ID = "openai/gpt-oss-20b"


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subquestions: list[str] = Field(
        min_length=4,
        max_length=6,
    )
    success_criteria: list[str] = Field(
        min_length=3,
        max_length=5,
    )


def build_planner_prompt(request: ResearchRequest) -> str:
    context = request.context or "No additional context provided."

    return f"""
Decision question:
{request.question}

Company or industry context:
{context}

Decision horizon:
{request.horizon}

Create a focused research plan for this decision.
Do not answer the decision question yet.
Do not invent facts, statistics, companies, or sources.
""".strip()


async def create_research_plan(
    request: ResearchRequest,
) -> ResearchResponse:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY was not found. Check the .env file."
        )

    client = AsyncGroq(api_key=api_key)

    response = await client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the planning component of an "
                    "evidence-grounded business research agent. "
                    "Break business decisions into specific, "
                    "researchable subquestions. Cover customer needs, "
                    "strategic alternatives, market evidence, "
                    "operational and financial viability, risks, and "
                    "decision thresholds when relevant. Success "
                    "criteria must be observable and decision-relevant. "
                    "Use the same language as the user's question."
                ),
            },
            {
                "role": "user",
                "content": build_planner_prompt(request),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "research_plan",
                "strict": True,
                "schema": PlannerOutput.model_json_schema(),
            },
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "The model returned an empty planning response."
        )

    planner_output = PlannerOutput.model_validate(
        json.loads(content)
    )

    plan = ResearchPlan(
        decision_question=request.question,
        context=request.context,
        horizon=request.horizon,
        subquestions=planner_output.subquestions,
        success_criteria=planner_output.success_criteria,
    )

    return ResearchResponse(
        status="completed",
        stage="planning",
        plan=plan,
    )