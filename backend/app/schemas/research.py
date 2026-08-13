from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    dataset_id: str
    name: str
    source: str
    license: str
    version: str
    row_count: int
    feature_count: int
    date_range: list[str] | None
    preprocessing: list[str]
    limitations: list[str]
    evidence_level: str


class RunExperimentRequest(BaseModel):
    experiment_type: str
    configuration: dict = Field(default_factory=dict)


class ExperimentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    experiment_name: str
    experiment_type: str
    dataset_version: str | None
    model_version: str | None
    configuration_json: dict
    metrics_json: dict
    random_seed: int | None
    status: str
    created_at: datetime


class ExportRequest(BaseModel):
    table: str
    format: str
    experiment_id: str | None = None
