"""Optional live smoke test for the industry research pipeline.

Run locally only after setting GROQ_API_KEY and TAVILY_API_KEY.
Do not run this in GitHub Actions without explicitly configured secrets.
Prints source metadata only, not API keys or full research content.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from src.llm_provider import get_provider, has_llm_credentials
from src.models import ResearchRequest
from src.workflow import run_research


async def main() -> int:
    load_dotenv()
    if not has_llm_credentials() or not os.getenv("TAVILY_API_KEY"):
        print("SKIP: configure the selected LLM provider and Tavily keys.")
        return 2
    print(f"LLM provider: {get_provider()}")

    request = ResearchRequest(
        mode="industry",
        question="中国商业银行行业的主要盈利模式、竞争格局和发展风险是什么？",
        context="中国市场；优先使用监管机构、公开年报及官方统计",
        horizon="12 months",
    )
    try:
        result = await run_research(request)
    except Exception as exc:
        print(f"FAIL: pipeline error ({type(exc).__name__}).")
        return 1

    source_ids = [src.source_id for src in result.reviewed_sources]
    assessment_ids = [item.source_id for item in result.assessments]
    referenced = {
        source_id
        for finding in result.brief.key_findings
        for source_id in finding.source_ids
    } if result.brief else set()
    page_excerpts = sum(
        src.content_origin == "page_excerpt"
        for src in result.reviewed_sources
    )

    print(f"Mode: {result.plan.mode}")
    print(f"Sources: {len(source_ids)}")
    print(f"Page excerpts: {page_excerpts}")
    print(f"Assessments: {len(assessment_ids)}")
    print(f"Referenced IDs: {len(referenced)}")
    print(f"Confidence: {result.brief.confidence if result.brief else 'missing'}")
    print("Note: this smoke test checks pipeline behavior, not factual accuracy.")

    if not result.brief or result.plan.mode != "industry":
        print("FAIL: missing or wrong-mode report.")
        return 1
    if len(source_ids) < 3 or len(source_ids) != len(set(source_ids)):
        print("FAIL: insufficient or duplicate evidence source IDs.")
        return 1
    if source_ids != assessment_ids:
        print("FAIL: review assessments do not match source IDs.")
        return 1
    if not referenced or not referenced.issubset(set(source_ids)):
        print("FAIL: missing or invalid finding citations.")
        return 1
    if result.brief.executive_summary.startswith("系统已搜集部分证据，但"):
        print("FAIL: report generation fell back; check model API.")
        return 1
    if not page_excerpts:
        print("WARN: no page excerpts; the report relies on search snippets.")
    print("PASS: pipeline completed. Manually inspect factual grounding.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
