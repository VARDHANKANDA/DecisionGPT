"""Research Console — Dataset Registry with upload / validation / versioning
(docs/PRD.md §9).

Admin/researcher-only. Accepts CSV / XLSX / Parquet, runs the same
structural validation the training pipeline uses (ml/pipeline/validation.py),
inspects the schema, produces a data-quality report, and versions the
dataset (re-uploading the same name creates v2, v3, ...). Raw rows are
written under ``settings.research_data_path`` and are never served through
any SME-facing endpoint.
"""
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.research import ResearchDataset, ResearchDatasetVersion
from app.services import dataset_category
from ml.pipeline.validation import validate_dataframe

SUPPORTED_EXTENSIONS = {"csv", "xlsx", "parquet"}
DOMAINS = ["forecasting", "churn", "marketing", "pricing", "inventory", "causal", "benchmarks", "other"]


@dataclass
class ParsedUpload:
    dataframe: pd.DataFrame
    file_type: str


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "dataset"


def _storage_root() -> Path:
    root = Path(get_settings().research_data_path)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    return root


def parse_upload(filename: str, content: bytes) -> ParsedUpload:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValidationFailedError(
            f"Unsupported file type '.{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}."
        )
    try:
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(content))
        elif ext == "xlsx":
            df = pd.read_excel(io.BytesIO(content))
        else:  # parquet
            try:
                df = pd.read_parquet(io.BytesIO(content))
            except ImportError as exc:  # pragma: no cover - depends on env
                raise ValidationFailedError(
                    "Parquet support requires the 'pyarrow' package, which is not installed "
                    "in this environment. Upload CSV or XLSX instead."
                ) from exc
    except ValidationFailedError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface a clean message
        raise ValidationFailedError(f"Could not parse the uploaded file: {exc}") from exc

    if df.empty:
        raise ValidationFailedError("The uploaded file has no rows.")
    return ParsedUpload(dataframe=df, file_type=ext)


def _schema(df: pd.DataFrame) -> list[dict]:
    return [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]


def _missing_summary(df: pd.DataFrame) -> dict:
    return {str(c): int(df[c].isna().sum()) for c in df.columns if int(df[c].isna().sum()) > 0}


def _quality_report(df: pd.DataFrame) -> dict:
    # Treat every column as "required" for the generic report — this only
    # reports missing values / duplicates / emptiness, it does not reject.
    report = validate_dataframe(df, required_columns=list(df.columns))
    return {
        "row_count": report.row_count,
        "missing_columns": report.missing_columns,
        "missing_value_counts": report.missing_value_counts,
        "duplicate_row_count": report.duplicate_row_count,
        "issues": report.issues,
    }


def upload_dataset(
    db: Session,
    *,
    name: str,
    domain: str,
    filename: str,
    content: bytes,
    description: str | None = None,
    source: str | None = None,
    license: str | None = None,
    created_by: str | None = None,
) -> ResearchDatasetVersion:
    if domain not in DOMAINS:
        raise ValidationFailedError(f"Unknown domain '{domain}'. Expected one of {DOMAINS}.")

    parsed = parse_upload(filename, content)
    df = parsed.dataframe

    dataset_slug = _slugify(name)
    dataset = (
        db.query(ResearchDataset).filter(ResearchDataset.dataset_id == dataset_slug).one_or_none()
    )
    if dataset is None:
        dataset = ResearchDataset(
            dataset_id=dataset_slug,
            name=name,
            description=description,
            domain=domain,
            source=source,
            license=license,
            created_by=created_by,
        )
        db.add(dataset)
        db.flush()
        next_version = 1
    else:
        last = (
            db.query(ResearchDatasetVersion)
            .filter(ResearchDatasetVersion.dataset_id == dataset.id)
            .order_by(ResearchDatasetVersion.version.desc())
            .first()
        )
        next_version = (last.version + 1) if last else 1

    dest_dir = _storage_root() / dataset_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"v{next_version}.{parsed.file_type}"
    dest_path.write_bytes(content)

    quality = _quality_report(df)
    version_row = ResearchDatasetVersion(
        dataset_id=dataset.id,
        version=next_version,
        file_type=parsed.file_type,
        storage_path=str(dest_path.relative_to(_storage_root().parent)),
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        schema_json=_schema(df),
        missing_summary_json=_missing_summary(df),
        duplicates_summary_json={"duplicate_row_count": quality["duplicate_row_count"]},
        quality_report_json=quality,
        validation_ok=len(quality["issues"]) == 0,
        created_by=created_by,
    )
    db.add(version_row)
    db.commit()
    db.refresh(version_row)
    return version_row


def list_datasets(db: Session) -> list[dict]:
    out = []
    for ds in db.query(ResearchDataset).order_by(ResearchDataset.created_at.desc()).all():
        versions = (
            db.query(ResearchDatasetVersion)
            .filter(ResearchDatasetVersion.dataset_id == ds.id)
            .order_by(ResearchDatasetVersion.version.desc())
            .all()
        )
        out.append(
            {
                "id": ds.id,
                "dataset_id": ds.dataset_id,
                "name": ds.name,
                "description": ds.description,
                "domain": ds.domain,
                "source": ds.source,
                "license": ds.license,
                "data_category": dataset_category.classify(
                    source=ds.source, dataset_id=ds.dataset_id
                ),
                "created_at": ds.created_at,
                "created_by": ds.created_by,
                "version_count": len(versions),
                "latest_version": versions[0].version if versions else None,
                "versions": [_version_dict(v) for v in versions],
            }
        )
    return out


def _version_dict(v: ResearchDatasetVersion) -> dict:
    return {
        "id": v.id,
        "dataset_id": v.dataset_id,
        "version": v.version,
        "file_type": v.file_type,
        "row_count": v.row_count,
        "column_count": v.column_count,
        "columns": v.schema_json,
        "missing_summary": v.missing_summary_json,
        "duplicates_summary": v.duplicates_summary_json,
        "quality_report": v.quality_report_json,
        "validation_ok": v.validation_ok,
        "created_at": v.created_at,
        "created_by": v.created_by,
    }


def get_version(db: Session, version_id: str) -> ResearchDatasetVersion:
    v = db.get(ResearchDatasetVersion, version_id)
    if v is None:
        raise NotFoundError(f"Dataset version {version_id} not found.")
    return v


def version_dict(v: ResearchDatasetVersion) -> dict:
    return _version_dict(v)


def load_version_dataframe(v: ResearchDatasetVersion) -> pd.DataFrame:
    path = _storage_root().parent / v.storage_path
    if not path.exists():
        raise NotFoundError(f"Stored file for dataset version {v.id} is missing at {path}.")
    if v.file_type == "csv":
        return pd.read_csv(path)
    if v.file_type == "xlsx":
        return pd.read_excel(path)
    return pd.read_parquet(path)
