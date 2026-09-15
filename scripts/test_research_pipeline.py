import asyncio

from src.models import ResearchRequest
from src.search_tool import search_web
from src.workflow import create_research_plan


async def main():
    request = ResearchRequest(
        question=(
            "Should a regional retailer launch "
            "same-day delivery?"
        ),
        context=(
            "The company operates in Shenyang "
            "and has a limited logistics budget."
        ),
        horizon="90 days",
    )

    planning_response = await create_research_plan(request)
    plan = planning_response.plan

    print("\nGenerated search queries:")

    for index, query in enumerate(
        plan.search_queries,
        start=1,
    ):
        print(f"{index}. {query}")

    # 测试阶段只使用前3个检索词，节省Tavily额度。
    selected_queries = plan.search_queries[:3]

    evidence_bundles = await asyncio.gather(
        *[
            search_web(
                query=query,
                max_results=2,
            )
            for query in selected_queries
        ]
    )

    print("\nCollected evidence:")

    for bundle in evidence_bundles:
        print(f"\nQUERY: {bundle.query}")

        if not bundle.records:
            print("No evidence found.")
            continue

        for record in bundle.records:
            print(f"- {record.title}")
            print(f"  URL: {record.url}")
            print(
                "  Relevance score: "
                f"{record.relevance_score:.3f}"
            )


if __name__ == "__main__":
    asyncio.run(main())