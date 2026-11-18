"""Best-effort retrieval of page excerpts for selected public search results.

Uses Tavily Extract rather than direct requests to arbitrary URLs. Extraction
failures leave original search snippets intact. Retrieved pages are untrusted
third-party text, not instructions to the language model.
"""

import os
import re

from tavily import AsyncTavilyClient

from .models import EvidenceBundle
from .reviewer import canonical_source_url, prepare_evidence


def select_page_excerpt(raw_content: str, limit: int = 2200) -> str:
    """Return a bounded, readable excerpt; not a verified full document."""
    if not isinstance(raw_content, str):
        return ""
    cleaned = re.sub(r"\s+", " ", raw_content).strip()
    if len(cleaned) < 160:
        return ""
    return cleaned[:limit]


async def enrich_evidence(
    bundles: list[EvidenceBundle],
    max_pages: int = 4,
    client: AsyncTavilyClient | None = None,
) -> list[EvidenceBundle]:
    """Enrich up to max_pages unique selected URLs; gracefully keep snippets."""
    if not bundles or max_pages <= 0:
        return bundles

    selected = prepare_evidence(bundles)[:max_pages]
    selected_urls = [
        src["url"]
        for src in selected
        if canonical_source_url(src["url"])
    ]
    if not selected_urls:
        return bundles

    if client is None:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            return bundles
        client = AsyncTavilyClient(api_key=key)

    try:
        response = await client.extract(
            urls=selected_urls,
            extract_depth="basic",
        )
    except Exception as error:
        print(f"Source extraction unavailable: {type(error).__name__}")
        return bundles

    if not isinstance(response, dict):
        return bundles

    extracted_by_url = {}
    allowed_urls = {
        canonical_source_url(url) for url in selected_urls
    }
    for result in response.get("results", []):
        if not isinstance(result, dict):
            continue
        canonical = canonical_source_url(str(result.get("url", "")))
        if canonical not in allowed_urls:
            continue
        excerpt = select_page_excerpt(result.get("raw_content", ""))
        if excerpt:
            extracted_by_url[canonical] = excerpt

    # Never overwrite the source URL or its search metadata.
    enriched_bundles = []
    for bundle in bundles:
        enriched_records = []
        for record in bundle.records:
            key = canonical_source_url(record.url)
            if key in extracted_by_url:
                enriched_records.append(
                    record.model_copy(
                        update={
                            "excerpt": extracted_by_url[key],
                            "content_origin": "page_excerpt",
                        }
                    )
                )
            else:
                enriched_records.append(record)
        enriched_bundles.append(
            bundle.model_copy(update={"records": enriched_records})
        )
    return enriched_bundles
