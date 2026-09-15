import os

from dotenv import load_dotenv
from tavily import AsyncTavilyClient

from .models import EvidenceBundle, EvidenceRecord


load_dotenv()


async def search_web(
    query: str,
    max_results: int = 3,
    min_score: float = 0.25,
) -> EvidenceBundle:
    query = query.strip()

    if not query:
        raise ValueError("检索词不能为空。")

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "未找到 TAVILY_API_KEY，请检查环境变量配置。"
        )

    client = AsyncTavilyClient(api_key=api_key)

    safe_max_results = max(1, min(max_results, 5))

    response = await client.search(
        query=query,
        search_depth="basic",
        max_results=safe_max_results,
        include_answer=False,
        include_raw_content=False,
    )

    records = []

    for item in response.get("results", []):
        url = item.get("url")

        if not url:
            continue

        score = item.get("score")
        score_value = (
            float(score)
            if score is not None
            else 0.0
        )

        if score_value < min_score:
            continue

        records.append(
            EvidenceRecord(
                title=item.get("title") or "未命名来源",
                url=url,
                excerpt=item.get("content") or "",
                relevance_score=score_value,
                query=query,
            )
        )

    return EvidenceBundle(
        query=query,
        records=records,
    )
