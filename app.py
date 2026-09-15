from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.models import ResearchRequest, ResearchResponse
from src.workflow import create_research_plan


app = FastAPI(
    title="Business Research Decision Agent",
    description=(
        "An evidence-grounded agent for business research "
        "and decision support."
    ),
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
    return create_research_plan(request)


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)