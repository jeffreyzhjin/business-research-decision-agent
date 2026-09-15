import asyncio
import json
import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv
from groq import AsyncGroq

from .models import (
    EvidenceAssessment,
    EvidenceBundle,
    EvidenceLevel,
    SourceType,
)


load_dotenv()

MODEL_ID = "openai/gpt-oss-20b"


def prepare_evidence(
    evidence_bundles: list[EvidenceBundle],
) -> list[dict]:
    prepared_sources = []
    source_number = 1

    for bundle in evidence_bundles:
        ranked_records = sorted(
            bundle.records,
            key=lambda record: record.relevance_score,
            reverse=True,
        )

        # 每个检索词只保留相关性最高的一条结果。
        for record in ranked_records[:1]:
            prepared_sources.append(
                {
                    "source_id": f"S{source_number}",
                    "query": bundle.query,
                    "title": record.title,
                    "url": record.url,
                    "excerpt": record.excerpt[:600],
                    "search_relevance_score": (
                        record.relevance_score
                    ),
                }
            )
            source_number += 1

    return prepared_sources


def infer_source_type(
    url: str,
    title: str,
) -> SourceType:
    host = urlparse(url).netloc.lower()
    title_lower = title.lower()

    if ".gov.cn" in host:
        return "government"

    if any(
        marker in host
        for marker in (
            ".edu.",
            ".edu.cn",
            ".ac.cn",
            "doi.org",
        )
    ):
        return "academic"

    if any(
        keyword in title_lower
        for keyword in (
            "report",
            "white paper",
            "research",
            "研究报告",
            "白皮书",
        )
    ):
        return "industry_report"

    if any(
        marker in host
        for marker in (
            "people.com.cn",
            "xinhuanet.com",
            "cnr.cn",
            "reuters.com",
            "bbc.com",
        )
    ):
        return "news"

    if any(
        marker in host
        for marker in (
            "shopify.com",
            "meituan.com",
            "jd.com",
            "alibaba.com",
        )
    ):
        return "company"

    return "other"


def compact_excerpt(
    excerpt: str,
    title: str,
    max_length: int = 180,
) -> str:
    cleaned = re.sub(r"\s+", " ", excerpt).strip()

    if not cleaned:
        return title.strip()

    if len(cleaned) <= max_length:
        return cleaned

    shortened = cleaned[:max_length].rstrip(
        " ,，;；:："
    )
    return f"{shortened}…"


def build_fallback_assessment(
    source: dict,
) -> EvidenceAssessment:
    source_type = infer_source_type(
        url=str(source["url"]),
        title=str(source["title"]),
    )

    if source_type in {
        "government",
        "academic",
    }:
        quality: EvidenceLevel = "high"
    elif source_type in {
        "industry_report",
        "company",
        "news",
    }:
        quality = "medium"
    else:
        quality = "low"

    score = float(
        source["search_relevance_score"]
    )

    if score >= 0.60:
        relevance: EvidenceLevel = "high"
    elif score >= 0.35:
        relevance = "medium"
    else:
        relevance = "low"

    return EvidenceAssessment(
        source_id=str(source["source_id"]),
        source_type=source_type,
        quality=quality,
        relevance=relevance,
        key_claim=compact_excerpt(
            excerpt=str(source["excerpt"]),
            title=str(source["title"]),
        ),
        limitations=(
            "Rule-based fallback assessment was used for "
            "this source. The claim requires manual "
            "verification."
        ),
    )


def build_fallback_assessments(
    prepared_sources: list[dict],
) -> list[EvidenceAssessment]:
    return [
        build_fallback_assessment(source)
        for source in prepared_sources
    ]


async def review_single_source(
    client: AsyncGroq,
    source: dict,
    semaphore: asyncio.Semaphore,
) -> EvidenceAssessment:
    source_id = str(source["source_id"])

    source_json = json.dumps(
        source,
        ensure_ascii=False,
        indent=2,
    )

    try:
        async with semaphore:
            response = await (
                client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You review one evidence "
                                "source for a business "
                                "decision. Return only one "
                                "JSON object with exactly "
                                "these fields: source_id, "
                                "source_type, quality, "
                                "relevance, key_claim, and "
                                "limitations. Preserve the "
                                "supplied source_id exactly. "
                                "Allowed source_type values "
                                "are government, academic, "
                                "industry_report, company, "
                                "news, or other. Allowed "
                                "quality and relevance values "
                                "are high, medium, or low. "
                                "Write key_claim as one "
                                "concise sentence directly "
                                "supported by the excerpt. "
                                "Do not copy navigation text "
                                "or long passages. Do not "
                                "invent facts. Mention missing "
                                "dates, weak authority, "
                                "commercial bias, or indirect "
                                "relevance when applicable. "
                                "Use the same language as the "
                                "supplied evidence."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "Assess this source and return "
                                "the required JSON object:"
                                "\n\n"
                                f"{source_json}"
                            ),
                        },
                    ],
                    response_format={
                        "type": "json_object",
                    },
                    temperature=0.1,
                    reasoning_effort="low",
                    max_completion_tokens=900,
                )
            )

        content = response.choices[0].message.content

        if not content:
            raise ValueError(
                "The AI reviewer returned empty content."
            )

        assessment = (
            EvidenceAssessment.model_validate_json(
                content
            )
        )

        if assessment.source_id != source_id:
            raise ValueError(
                "The AI reviewer changed the source_id."
            )

        return assessment

    except Exception as error:
        print(
            f"Evidence reviewer fallback for "
            f"{source_id}: {error}"
        )

        return build_fallback_assessment(source)


async def review_evidence(
    evidence_bundles: list[EvidenceBundle],
) -> list[EvidenceAssessment]:
    prepared_sources = prepare_evidence(
        evidence_bundles
    )

    if not prepared_sources:
        return []

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print(
            "Evidence reviewer fallback: "
            "GROQ_API_KEY was not found."
        )

        return build_fallback_assessments(
            prepared_sources
        )

    client = AsyncGroq(api_key=api_key)

    # 最多同时审查两条，兼顾速度和免费 API 限制。
    semaphore = asyncio.Semaphore(2)

    tasks = [
        review_single_source(
            client=client,
            source=source,
            semaphore=semaphore,
        )
        for source in prepared_sources
    ]

    assessments = await asyncio.gather(*tasks)

    return list(assessments)