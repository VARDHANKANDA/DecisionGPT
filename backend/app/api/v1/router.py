from fastapi import APIRouter, Depends

from app.api.deps import verify_business_access
from app.api.v1.endpoints import (
    analytics,
    assistant,
    auth,
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
from app.api.v1.endpoints.research import overview as research_overview
from app.api.v1.endpoints.research import training as research_training

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(businesses.router, tags=["businesses"])

# Every route below is scoped to a single /businesses/{business_id}/** and
# is guarded by verify_business_access (existence + ownership when auth is on).
_scoped = [
    (data.router, "data"),
    (analytics.router, "analytics"),
    (goals.router, "goals"),
    (digital_twin.router, "digital-twin"),
    (causal_graph.router, "causal-graph"),
    (decisions.router, "decisions"),
    (memory.router, "memory"),
    (assistant.router, "assistant"),
]
for _router, _tag in _scoped:
    api_router.include_router(_router, tags=[_tag], dependencies=[Depends(verify_business_access)])

api_router.include_router(research_overview.router, prefix="/research", tags=["research"])
api_router.include_router(research_models.router, prefix="/research", tags=["research"])
api_router.include_router(research_datasets.router, prefix="/research", tags=["research"])
api_router.include_router(research_training.router, prefix="/research", tags=["research"])
api_router.include_router(research_experiments.router, prefix="/research", tags=["research"])
api_router.include_router(research_export.router, prefix="/research", tags=["research"])
