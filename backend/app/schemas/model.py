from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    model_name: str
    model_type: str
    version: str
    dataset_version: str
    feature_version: str
    parameters_json: dict
    metrics_json: dict
    model_path: str
    status: str
    created_at: datetime
