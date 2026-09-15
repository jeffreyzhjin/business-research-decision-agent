import asyncio

from src.search_tool import search_web


async def main():
    bundle = await search_web(
        query="Who is Lionel Messi?",
        max_results=3,
    )

    print(bundle.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())