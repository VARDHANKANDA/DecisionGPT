from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.schemas.research import DatasetsResponse, DatasetVersionOut
from app.services import dataset_registry_service, research_dataset_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/datasets", response_model=DatasetsResponse)
def list_datasets(db: Session = Depends(get_db)):
    """Both dataset sources, kept clearly separate:
    - ``platform``  : the bundled/documented datasets under data/platform/**
    - ``uploaded``  : datasets a researcher uploaded through this console
    Never reachable from any SME-facing route.
    """
    return {
        "platform": dataset_registry_service.list_datasets(),
        "external": dataset_registry_service.list_external_datasets(),
        "uploaded": research_dataset_service.list_datasets(db),
    }


@router.post("/datasets/upload", response_model=DatasetVersionOut, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    domain: str = Form(...),
    description: str | None = Form(None),
    source: str | None = Form(None),
    license: str | None = Form(None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    version = research_dataset_service.upload_dataset(
        db,
        name=name,
        domain=domain,
        filename=file.filename or "upload.csv",
        content=content,
        description=description,
        source=source,
        license=license,
    )
    return research_dataset_service.version_dict(version)


@router.get("/datasets/versions/{version_id}", response_model=DatasetVersionOut)
def get_dataset_version(version_id: str, db: Session = Depends(get_db)):
    return research_dataset_service.version_dict(
        research_dataset_service.get_version(db, version_id)
    )
