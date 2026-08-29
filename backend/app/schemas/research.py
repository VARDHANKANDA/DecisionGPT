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
    data_category: str = "UNCLASSIFIED"


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
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    model_versions_json: dict | None = None
    created_at: datetime


class ExportRequest(BaseModel):
    table: str
    format: str
    experiment_id: str | None = None


# ---- Dataset registry (uploaded) ----------------------------------------


class DatasetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    version: int
    file_type: str
    row_count: int
    column_count: int
    columns: list[dict]
    missing_summary: dict
    duplicates_summary: dict
    quality_report: dict
    validation_ok: bool
    created_at: datetime
    created_by: str | None = None


class UploadedDatasetOut(BaseModel):
    id: str
    dataset_id: str
    name: str
    description: str | None
    domain: str
    source: str | None
    license: str | None
    data_category: str = "UNCLASSIFIED"
    created_at: datetime
    created_by: str | None
    version_count: int
    latest_version: int | None
    versions: list[DatasetVersionOut]


class ExternalDatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_id: str
    name: str
    display_label: str
    data_category: str
    status: str
    source: str
    license: str
    geography: str
    business_domain: str
    date_range: str | None
    supported_tasks: list[str]
    limitations: list[str]


class DatasetsResponse(BaseModel):
    platform: list[DatasetEntryOut]
    external: list[ExternalDatasetOut]
    uploaded: list[UploadedDatasetOut]


# ---- Training center --------------------------------------------------


class RunTrainingRequest(BaseModel):
    task: str
    model_type: str
    dataset_version_id: str | None = None
    platform_domain: str | None = None
    parameters: dict = Field(default_factory=dict)
    seed: int = 42


class TrainingRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_version_id: str | None
    platform_domain: str | None
    dataset_version_label: str | None
    task: str
    model_type: str
    features_json: list
    target: str | None
    parameters_json: dict
    random_seed: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    metrics_json: dict
    model_id: str | None
    model_name: str | None
    model_version: str | None
    artifact_path: str | None
    error_message: str | None
    created_at: datetime


class ModelStatusRequest(BaseModel):
    pass


# ---- Overview -------------------------------------------------------


class ResearchOverviewOut(BaseModel):
    uploaded_dataset_count: int
    uploaded_dataset_version_count: int
    platform_dataset_count: int
    model_count: int
    active_model_count: int
    experimental_model_count: int
    training_run_count: int
    training_runs_failed: int
    experiment_count: int
    experiments_completed: int
    experiments_failed: int
    latest_experiment: dict | None
    best_metrics: dict
