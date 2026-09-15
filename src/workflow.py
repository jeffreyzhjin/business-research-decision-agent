from src.models import (
    ResearchPlan,
    ResearchRequest,
    ResearchResponse,
)


def create_research_plan(
    request: ResearchRequest,
) -> ResearchResponse:
    context = (
        request.context.strip()
        or "General business context"
    )

    subquestions = [
        "What customer or stakeholder problem creates the need?",
        "What strategic options and alternatives should be compared?",
        "What market, operational, and financial evidence is required?",
        "Which risks, constraints, and assumptions could change the decision?",
        "What result would justify action within the decision horizon?",
    ]

    success_criteria = [
        "Important claims can be traced to evidence.",
        "Alternatives are compared using explicit criteria.",
        "Uncertainty and unsupported assumptions are identified.",
        f"The recommendation is actionable within {request.horizon}.",
    ]

    plan = ResearchPlan(
        decision_question=request.question.strip(),
        context=context,
        horizon=request.horizon,
        subquestions=subquestions,
        success_criteria=success_criteria,
    )

    return ResearchResponse(
        status="completed",
        stage="planning",
        plan=plan,
    )