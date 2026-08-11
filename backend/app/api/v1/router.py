from fastapi import APIRouter

from app.api.v1.endpoints import analytics, businesses, causal_graph, data, decisions, digital_twin, goals, health
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
api_router.include_router(
    research_models.router, prefix="/research", tags=["research"]
)
