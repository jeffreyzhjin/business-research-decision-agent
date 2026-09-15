from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.models import ResearchRequest, ResearchResponse
from src.workflow import run_research


app = FastAPI(
    title="商业研究决策助手",
    description="基于可追溯证据的商业研究与决策支持工具。",
    version="0.2.0",
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "business-research-decision-agent",
    }


@app.post(
    "/api/research",
    response_model=ResearchResponse,
)
async def research(
    request: ResearchRequest,
) -> ResearchResponse:
    return await run_research(request)


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)
