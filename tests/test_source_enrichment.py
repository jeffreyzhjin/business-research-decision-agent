"""Offline tests for source enrichment and safe fallback."""

import unittest

from src.models import EvidenceBundle, EvidenceRecord
from src.source_enrichment import enrich_evidence, select_page_excerpt


class FakeExtractClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def extract(self, *, urls, extract_depth):
        self.calls.append((urls, extract_depth))
        if self.error:
            raise self.error
        return self.response


def item(url, text="Search result"):
    return EvidenceRecord(
        title="Source",
        url=url,
        excerpt=text,
        relevance_score=0.9,
        query="industry",
    )


class SourceEnrichmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_bounded_excerpt(self):
        raw = "Independent annual report details. " * 130
        client = FakeExtractClient({
            "results": [{
                "url": "https://example.com/report",
                "raw_content": raw,
            }]
        })
        bundles = [EvidenceBundle(
            query="industry",
            records=[item("https://example.com/report")],
        )]
        result = await enrich_evidence(bundles, client=client)
        record = result[0].records[0]
        self.assertEqual(record.content_origin, "page_excerpt")
        self.assertGreater(len(record.excerpt), 160)
        self.assertLessEqual(len(record.excerpt), 2200)
        self.assertEqual(bundles[0].records[0].content_origin, "search_snippet")
        self.assertEqual(client.calls[0][1], "basic")

    async def test_failed_extraction_preserves_search_snippet(self):
        client = FakeExtractClient(error=RuntimeError("network failure"))
        bundles = [EvidenceBundle(
            query="industry",
            records=[item("https://example.com/report", "Original snippet")],
        )]
        result = await enrich_evidence(bundles, client=client)
        self.assertEqual(result[0].records[0].excerpt, "Original snippet")
        self.assertEqual(result[0].records[0].content_origin, "search_snippet")

    async def test_ignores_unrequested_url(self):
        client = FakeExtractClient({
            "results": [{
                "url": "https://not-our-source.com/page",
                "raw_content": "Untrusted content " * 100,
            }]
        })
        bundles = [EvidenceBundle(
            query="industry",
            records=[item("https://example.com/report", "Original snippet")],
        )]
        result = await enrich_evidence(bundles, client=client)
        self.assertEqual(result[0].records[0].excerpt, "Original snippet")

    async def test_short_content_retains_snippet(self):
        client = FakeExtractClient({
            "results": [{
                "url": "https://example.com/report",
                "raw_content": "Just navigation",
            }]
        })
        bundles = [EvidenceBundle(
            query="industry",
            records=[item("https://example.com/report", "Original snippet")],
        )]
        result = await enrich_evidence(bundles, client=client)
        self.assertEqual(result[0].records[0].content_origin, "search_snippet")

    async def test_extraction_budget(self):
        bundles = [
            EvidenceBundle(query=str(i), records=[
                item(f"https://example.com/{i}")
            ])
            for i in range(8)
        ]
        client = FakeExtractClient({"results": []})
        await enrich_evidence(bundles, max_pages=4, client=client)
        self.assertEqual(len(client.calls[0][0]), 4)

    def test_excerpt_empty_for_short_or_invalid_content(self):
        self.assertEqual(select_page_excerpt("short"), "")
        self.assertEqual(select_page_excerpt(None), "")


if __name__ == "__main__":
    unittest.main()
