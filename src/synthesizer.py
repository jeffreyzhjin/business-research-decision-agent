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
                    "The available search evidence is "
                    "insufficient for a reliable decision."
                ),
                source_ids=[],
            )
        ]

    return DecisionBrief(
        executive_summary=(
            "Evidence was collected, but the automated "
            "decision synthesis was unavailable or could "
            "not be validated. The available material "
            "should be treated as preliminary."
        ),
        recommendation=(
            "Do not make an irreversible decision yet. "
            "Validate the most important assumptions "
            "through additional primary research or a "
            "limited pilot."
        ),
        confidence="low",
        key_findings=key_findings,
        alternatives=[
            "Run a limited and measurable pilot.",
            "Delay the decision until stronger evidence is available.",
            "Maintain the current approach while collecting data.",
        ],
        risks=[
            "Available sources may not represent the local market.",
            "Search excerpts may omit important context.",
            "Important financial assumptions remain unverified.",
        ],
        next_steps=[
            "Open and verify all high- and medium-quality sources.",
            "Collect primary customer and operational data.",
            "Define measurable decision thresholds.",
            "Update the analysis when stronger evidence is available.",
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
                        "You are the decision synthesis "
                        "component of an evidence-grounded "
                        "business research agent. Use only "
                        "the supplied sources and assessments. "
                        "Do not invent facts, statistics, or "
                        "citations. Treat success criteria as "
                        "proposed decision thresholds, not as "
                        "established facts. Every key finding "
                        "must cite one or more valid source_ids. "
                        "If evidence is weak or incomplete, "
                        "say so and lower confidence. Use the "
                        "same language as the decision question. "
                        "Return only one valid JSON object."
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
                        "Allowed confidence values are "
                        "high, medium, or low.\n\n"
                        "Research material:\n"
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