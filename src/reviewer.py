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


def contains_chinese(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


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

    excerpt = str(source["excerpt"])
    title = str(source["title"])

    if contains_chinese(excerpt):
        key_claim = compact_excerpt(
            excerpt=excerpt,
            title=title,
        )
    else:
        key_claim = (
            f"来源《{title}》与当前检索词相关，但未完成 AI 中文评估；"
            "请打开原文核验其具体结论。"
        )

    return EvidenceAssessment(
        source_id=str(source["source_id"]),
        source_type=source_type,
        quality=quality,
        relevance=relevance,
        key_claim=key_claim,
        limitations=(
            "该来源使用了规则评估，因为 AI 评估暂时不可用；"
            "相关观点仍需人工核验。"
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
                                "你负责评估一条用于商业决策的证据。"
                                "只返回一个 JSON 对象，且仅包含 source_id、"
                                "source_type、quality、relevance、key_claim "
                                "和 limitations 字段。必须原样保留 source_id。"
                                "source_type 只能是 government、academic、"
                                "industry_report、company、news 或 other；"
                                "quality 和 relevance 只能是 high、medium 或 low。"
                                "key_claim 和 limitations 必须使用简体中文。"
                                "key_claim 用一句简洁中文概括摘要直接支持的观点。"
                                "不要复制导航文字或长段落，不得虚构事实。"
                                "如存在日期缺失、来源权威性不足、商业偏向或"
                                "间接相关等问题，应在 limitations 中明确说明。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "评估以下来源并返回规定的 JSON 对象："
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
