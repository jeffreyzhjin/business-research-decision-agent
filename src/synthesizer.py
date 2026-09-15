import json
import os

from dotenv import load_dotenv
from groq import AsyncGroq

from .models import (
    CitedFinding,
    DecisionBrief,
    EvidenceAssessment,
    EvidenceBundle,
    ResearchPlan,
    ResearchRequest,
)
from .reviewer import prepare_evidence


load_dotenv()

MODEL_ID = "openai/gpt-oss-20b"


def build_fallback_brief(
    assessments: list[EvidenceAssessment],
) -> DecisionBrief:
    usable_assessments = [
        assessment
        for assessment in assessments
        if assessment.relevance in {
            "high",
            "medium",
        }
    ]

    key_findings = [
        CitedFinding(
            claim=assessment.key_claim,
            source_ids=[assessment.source_id],
        )
        for assessment in usable_assessments[:5]
    ]

    if not key_findings:
        key_findings = [
            CitedFinding(
                claim=(
                    "现有检索证据不足以支持可靠决策。"
                ),
                source_ids=[],
            )
        ]

    return DecisionBrief(
        executive_summary=(
            "系统已搜集部分证据，但自动决策综合暂时不可用或未通过验证。"
            "当前材料只能作为初步参考。"
        ),
        recommendation=(
            "暂不作出不可逆决策。建议通过补充一手调研或开展小范围试点，"
            "验证最关键的假设。"
        ),
        confidence="low",
        key_findings=key_findings,
        alternatives=[
            "开展范围有限且可量化评估的试点。",
            "推迟决策，等待更有力的证据。",
            "在继续收集数据期间维持现有方案。",
        ],
        risks=[
            "现有来源可能不能代表本地市场。",
            "搜索摘要可能遗漏重要上下文。",
            "关键财务假设仍未得到验证。",
        ],
        next_steps=[
            "打开并核验所有高质量和中等质量来源。",
            "收集客户与运营方面的一手数据。",
            "设定可量化的决策阈值。",
            "获得更有力的证据后更新分析。",
        ],
    )


async def synthesize_decision(
    request: ResearchRequest,
    plan: ResearchPlan,
    evidence: list[EvidenceBundle],
    assessments: list[EvidenceAssessment],
) -> DecisionBrief:
    prepared_sources = prepare_evidence(evidence)

    if not prepared_sources or not assessments:
        return build_fallback_brief(assessments)

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print(
            "Decision synthesizer fallback: "
            "GROQ_API_KEY was not found."
        )
        return build_fallback_brief(assessments)

    synthesis_input = {
        "decision": {
            "question": request.question,
            "context": request.context,
            "horizon": request.horizon,
        },
        "research_plan": plan.model_dump(),
        "sources": prepared_sources,
        "evidence_assessments": [
            assessment.model_dump()
            for assessment in assessments
        ],
    }

    synthesis_json = json.dumps(
        synthesis_input,
        ensure_ascii=False,
        indent=2,
    )

    client = AsyncGroq(api_key=api_key)

    try:
        response = await client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是基于证据的商业研究助手中的决策综合模块。"
                        "只能使用给定来源和评估，不得虚构事实、统计数据或引用。"
                        "成功标准只是建议的决策阈值，不是已经成立的事实。"
                        "每项关键发现必须引用一个或多个有效 source_id。"
                        "如果证据薄弱或不完整，必须明确说明并降低置信度。"
                        "所有面向用户的文字，包括摘要、建议、发现、备选方案、"
                        "风险和下一步行动，都必须使用自然、清晰的简体中文。"
                        "只返回一个有效 JSON 对象。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Return exactly these JSON fields:\n"
                        "{\n"
                        '  "executive_summary": "...",\n'
                        '  "recommendation": "...",\n'
                        '  "confidence": "low",\n'
                        '  "key_findings": [\n'
                        "    {\n"
                        '      "claim": "...",\n'
                        '      "source_ids": ["S1"]\n'
                        "    }\n"
                        "  ],\n"
                        '  "alternatives": ["..."],\n'
                        '  "risks": ["..."],\n'
                        '  "next_steps": ["..."]\n'
                        "}\n\n"
                        "confidence 只能是 high、medium 或 low。\n\n"
                        "研究材料：\n"
                        f"{synthesis_json}"
                    ),
                },
            ],
            response_format={
                "type": "json_object",
            },
            temperature=0.1,
            reasoning_effort="low",
            max_completion_tokens=3000,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError(
                "The synthesizer returned empty content."
            )

        brief = DecisionBrief.model_validate_json(
            content
        )

        valid_source_ids = {
            str(source["source_id"])
            for source in prepared_sources
        }

        for finding in brief.key_findings:
            if not finding.source_ids:
                raise ValueError(
                    "A key finding has no source citation."
                )

            invalid_ids = (
                set(finding.source_ids)
                - valid_source_ids
            )

            if invalid_ids:
                raise ValueError(
                    "The synthesizer returned invalid "
                    f"source IDs: {invalid_ids}"
                )

        return brief

    except Exception as error:
        print(
            "Decision synthesizer fallback activated: "
            f"{error}"
        )
        return build_fallback_brief(assessments)
