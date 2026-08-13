from fastapi import APIRouter, Depends

from app.api.deps import require_research_access
from app.schemas.research import DatasetEntryOut
from app.services import dataset_registry_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/datasets", response_model=list[DatasetEntryOut])
def list_datasets():
    return dataset_registry_service.list_datasets()
