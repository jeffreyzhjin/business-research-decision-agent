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
    context = request.context or "未提供补充背景。"

    return f"""
决策问题：
{request.question}

企业或行业背景：
{context}

决策周期：
{request.horizon}

为这一决策制定聚焦、可执行的研究计划，暂时不要直接回答决策问题。
不得虚构事实、统计数据、企业或来源。

所有研究子问题和成功标准必须使用简体中文。
恰好生成6个简洁的网页检索词，使用关键词而不是完整问句。

采用分层检索策略：
- 2个针对具体本地市场的检索词；
- 2个针对全国行业基准或可比案例的检索词；
- 1个针对成本、单位经济性或财务可行性的检索词；
- 1个针对运营或监管风险的检索词。

当目标市场主要使用其他语言时，至少2个检索词使用当地语言；
其余检索词使用简体中文，也可使用英文寻找国际基准。
除非决策明确要求，否则不要强行添加年份。
避免所有检索词都过度狭窄而导致没有结果。
""".strip()


async def create_research_plan(
    request: ResearchRequest,
) -> ResearchResponse:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "未找到 GROQ_API_KEY，请检查环境变量配置。"
        )

    client = AsyncGroq(api_key=api_key)

    response = await client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是基于证据的商业研究助手中的研究规划模块。"
                    "请将商业决策拆分为具体、可研究的子问题，并在相关时"
                    "覆盖客户需求、备选策略、市场证据、运营与财务可行性、"
                    "风险和决策阈值。成功标准必须可观察且与决策直接相关。"
                    "无论用户以何种语言提问，所有解释性内容都使用自然、"
                    "清晰的简体中文。"
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
            "模型未返回研究计划。"
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
