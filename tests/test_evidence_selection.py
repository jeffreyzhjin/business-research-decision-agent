"""Offline tests for selection, deduplication and stable citation IDs."""

import unittest

from src.models import EvidenceBundle, EvidenceRecord, ResearchResponse, ResearchPlan
from src.reviewer import canonical_source_url, prepare_evidence


def record(url, score, query="banking"):
    return EvidenceRecord(
        title="Report",
        url=url,
        excerpt="Sample evidence",
        relevance_score=score,
        query=query,
    )


class EvidenceSelectionTests(unittest.TestCase):
    def test_tracking_variants_deduplicated(self):
        self.assertEqual(
            canonical_source_url("https://Example.com/report/?utm_source=x#section"),
            canonical_source_url("https://example.com/report"),
        )

    def test_invalid_scheme_rejected(self):
        self.assertEqual(canonical_source_url("javascript:alert(1)"), "")

    def test_source_selection_and_stable_ids(self):
        bundles = [
            EvidenceBundle(query="a", records=[
                record("https://example.org/first?utm_campaign=x", .90),
                record("https://example.org/second", .80),
                record("https://example.org/third", .70),
            ]),
            EvidenceBundle(query="b", records=[
                record("https://example.org/first", .99),
                record("https://example.org/fourth", .85),
            ]),
        ]
        sources = prepare_evidence(bundles)
        self.assertEqual([s["source_id"] for s in sources], ["S1", "S2", "S3"])
        self.assertEqual(
            [s["url"].split("?")[0] for s in sources],
            [
                "https://example.org/first",
                "https://example.org/second",
                "https://example.org/fourth",
            ],
        )

    def test_source_budget(self):
        bundles = [
            EvidenceBundle(query=str(i), records=[
                record(f"https://example.org/{i}-{j}", .9 - j * .1)
                for j in range(3)
            ])
            for i in range(8)
        ]
        sources = prepare_evidence(bundles)
        self.assertEqual(len(sources), 10)
        self.assertEqual(sources[-1]["source_id"], "S10")

    def test_response_exposes_source_reference(self):
        plan = ResearchPlan(
            decision_question="test",
            context="",
            horizon="90 days",
            subquestions=[],
            search_queries=[],
            success_criteria=[],
        )
        data = ResearchResponse(
            status="completed",
            stage="decision",
            plan=plan,
            reviewed_sources=[{
                "source_id": "S1",
                "query": "banking",
                "title": "Report",
                "url": "https://example.org/report",
                "excerpt": "Text",
                "search_relevance_score": .9,
            }],
        ).model_dump()
        self.assertEqual(data["reviewed_sources"][0]["source_id"], "S1")


if __name__ == "__main__":
    unittest.main()
