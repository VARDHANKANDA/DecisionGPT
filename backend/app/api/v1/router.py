from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    assistant,
    businesses,
    causal_graph,
    data,
    decisions,
    digital_twin,
    goals,
    health,
    memory,
)
from app.api.v1.endpoints.research import datasets as research_datasets
from app.api.v1.endpoints.research import experiments as research_experiments
from app.api.v1.endpoints.research import export as research_export
from app.api.v1.endpoints.research import models as research_models

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(businesses.router, tags=["businesses"])
api_router.include_router(data.router, tags=["data"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(goals.router, tags=["goals"])
api_router.include_router(digital_twin.router, tags=["digital-twin"])
api_router.include_router(causal_graph.router, tags=["causal-graph"])
api_router.include_router(decisions.router, tags=["decisions"])
api_router.include_router(memory.router, tags=["memory"])
api_router.include_router(assistant.router, tags=["assistant"])
api_router.include_router(research_models.router, prefix="/research", tags=["research"])
api_router.include_router(research_datasets.router, prefix="/research", tags=["research"])
api_router.include_router(research_experiments.router, prefix="/research", tags=["research"])
api_router.include_router(research_export.router, prefix="/research", tags=["research"])
