"""Full offline pipeline simulations using deterministic, synthetic API results.

No credentials, network calls, or live model outputs are involved.
These tests check orchestration, fallback reporting, and citation metadata.
"""

import os
import unittest
from unittest.mock import AsyncMock, patch

from src.models import (
    EvidenceBundle,
    EvidenceRecord,
    ResearchPlan,
    ResearchRequest,
    ResearchResponse,
)
from src.workflow import run_research


def plan_response(mode="industry"):
    plan = ResearchPlan(
        decision_question="中国银行业的盈利模式及竞争风险有哪些？",
        context="中国商业银行行业",
        horizon="12 months",
        subquestions=["行业结构是什么？"] * 4,
        search_queries=["banking policy", "banking earnings"],
        success_criteria=["能查证来源"] * 3,
        mode=mode,
    )
    return ResearchResponse(status="completed", stage="planning", plan=plan)


def record(url, excerpt="Synthetic banking data", score=0.9):
    return EvidenceRecord(
        title="Synthetic source (not a real report)",
        url=url,
        excerpt=excerpt,
        relevance_score=score,
        query="banking",
    )


class FakeExtractClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.called = False

    async def extract(self, *, urls, extract_depth):
        self.called = True
        if self.fail:
            raise RuntimeError("synthetic source service outage")
        return {
            "results": [
                {
                    "url": "https://example.org/banking",
                    "raw_content": "银行收入结构示意，仅用于模拟管道行为。 " * 90,
                }
            ]
        }


class PipelineSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_industry_mode_complete_pipeline_with_mock_services(self):
        client = FakeExtractClient()
        bundles = [
            EvidenceBundle(query="banking policy", records=[
                record("https://example.org/banking?utm_source=test"),
                record("https://example.org/other", "另一个示例来源"),
            ]),
            EvidenceBundle(query="banking earnings", records=[
                record("https://example.org/banking"),
                record("https://example.org/third", "第三个示例来源"),
            ]),
        ]
        with (
            patch.dict(os.environ, {
                "GROQ_API_KEY": "",
                "TAVILY_API_KEY": "test-key-not-used",
            }),
            patch("src.workflow.create_research_plan",
                  new_callable=AsyncMock,
                  return_value=plan_response()),
            patch("src.workflow.search_web", new_callable=AsyncMock,
                  side_effect=bundles) as search,
            patch("src.source_enrichment.AsyncTavilyClient",
                  return_value=client),
        ):
            result = await run_research(
                ResearchRequest(
                    question="中国银行业的盈利模式及竞争风险有哪些？",
                    mode="industry",
                )
            )

        self.assertEqual(search.await_count, 2)
        self.assertTrue(client.called)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.plan.mode, "industry")
        self.assertEqual(
            [src.source_id for src in result.reviewed_sources],
            ["S1", "S2", "S3"],
        )
        self.assertEqual(
            result.reviewed_sources[0].content_origin, "page_excerpt"
        )
        self.assertIsNone(result.reviewed_sources[0].published_date)
        self.assertEqual(
            [a.source_id for a in result.assessments], ["S1", "S2", "S3"]
        )
        self.assertEqual(result.brief.confidence, "low")
        self.assertEqual(
            [f.source_ids[0] for f in result.brief.key_findings],
            ["S1", "S2", "S3"],
        )
        self.assertIn("统计口径", result.brief.recommendation)

    async def test_search_partial_failure_and_extract_failure(self):
        client = FakeExtractClient(fail=True)
        bundles = EvidenceBundle(query="banking earnings", records=[
            record("https://example.org/other", "银行经营数据示例")
        ])
        with (
            patch.dict(os.environ, {
                "GROQ_API_KEY": "",
                "TAVILY_API_KEY": "test-key-not-used",
            }),
            patch("src.workflow.create_research_plan", new_callable=AsyncMock,
                  return_value=plan_response()),
            patch("src.workflow.search_web", new_callable=AsyncMock,
                  side_effect=[RuntimeError("search unavailable"), bundles]),
            patch("src.source_enrichment.AsyncTavilyClient",
                  return_value=client),
        ):
            result = await run_research(
                ResearchRequest(
                    question="中国银行业的盈利模式及竞争风险有哪些？",
                    mode="industry",
                )
            )
        self.assertEqual(len(result.evidence), 2)
        self.assertEqual(len(result.evidence[0].records), 0)
        self.assertEqual(len(result.reviewed_sources), 1)
        self.assertEqual(
            result.reviewed_sources[0].content_origin, "search_snippet"
        )
        self.assertEqual(result.brief.confidence, "low")

    async def test_all_searches_fail_safely(self):
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": ""}),
            patch("src.workflow.create_research_plan", new_callable=AsyncMock,
                  return_value=plan_response()),
            patch("src.workflow.search_web", new_callable=AsyncMock,
                  side_effect=RuntimeError("network down")),
        ):
            result = await run_research(
                ResearchRequest(
                    question="中国银行业的盈利模式及竞争风险有哪些？",
                    mode="industry",
                )
            )
        self.assertEqual(result.reviewed_sources, [])
        self.assertEqual(result.assessments, [])
        self.assertEqual(result.brief.confidence, "low")
        self.assertIn("证据不足", result.brief.recommendation)

    async def test_original_decision_mode_does_not_extract(self):
        bundles = EvidenceBundle(query="banking policy", records=[
            record("https://example.org/other", "银行服务流程示例")
        ])
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": ""}),
            patch("src.workflow.create_research_plan", new_callable=AsyncMock,
                  return_value=plan_response("decision")),
            patch("src.workflow.search_web", new_callable=AsyncMock,
                  side_effect=[bundles, bundles]),
            patch("src.workflow.enrich_evidence", new_callable=AsyncMock)
            as enrich,
        ):
            result = await run_research(
                ResearchRequest(
                    question="Should a bank open another branch?",
                    mode="decision",
                )
            )
        enrich.assert_not_awaited()
        self.assertEqual(result.plan.mode, "decision")
        self.assertEqual(result.brief.confidence, "low")
        self.assertIn("不可逆决策", result.brief.recommendation)


if __name__ == "__main__":
    unittest.main()
