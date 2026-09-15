import asyncio
import json
import os

from dotenv import load_dotenv
from groq import AsyncGroq
from pydantic import BaseModel, ConfigDict, Field

from .models import (
    EvidenceBundle,
    ResearchPlan,
    ResearchRequest,
    ResearchResponse,
)
from .search_tool import search_web
from .reviewer import review_evidence
from .synthesizer import synthesize_decision

load_dotenv()

MODEL_ID = "openai/gpt-oss-20b"


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subquestions: list[str] = Field(
        min_length=4,
        max_length=6,
    )
    search_queries: list[str] = Field(
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

Produce exactly 6 concise web search queries.
Write search queries as keywords, not full questions.

Use a layered search strategy:
- two queries for the specific local market;
- two queries for national industry benchmarks or comparable cases;
- one query for costs, unit economics, or financial viability;
- one query for operational or regulatory risks.

When the target market mainly uses another language,
write at least two queries in that market's local language.
The remaining queries may use the user's language.
Do not add a year unless the decision specifically requires one.
Avoid making every query so narrow that no results can be found.
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
        search_queries=planner_output.search_queries,
        success_criteria=planner_output.success_criteria,
    )

    return ResearchResponse(
        status="completed",
        stage="planning",
        plan=plan,
    )


async def run_research(
    request: ResearchRequest,
) -> ResearchResponse:
    planning_response = await create_research_plan(request)
    plan = planning_response.plan
    queries = plan.search_queries

    search_results = await asyncio.gather(
        *[
            search_web(
                query=query,
                max_results=3,
                min_score=0.25,
            )
            for query in queries
        ],
        return_exceptions=True,
    )

    evidence = []

    for query, result in zip(
        queries,
        search_results,
        strict=True,
    ):
        if isinstance(result, Exception):
            print(
                f"Search failed for query "
                f"{query!r}: {result}"
            )
            evidence.append(
                EvidenceBundle(
                    query=query,
                    records=[],
                )
            )
            continue

        evidence.append(result)

    assessments = await review_evidence(evidence)

    brief = await synthesize_decision(
        request=request,
        plan=plan,
        evidence=evidence,
        assessments=assessments,
    )

    return ResearchResponse(
        status="completed",
        stage="decision",
        plan=plan,
        evidence=evidence,
        assessments=assessments,
        brief=brief,
    )