"""Redirect research-platform file writes (uploaded datasets, trained model
artifacts) to a temp dir so the API test suite never pollutes the repo's
real data/ and models/ trees."""
import pytest

import ml.pipeline.registry as registry
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_research_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_data_path", str(tmp_path / "research_uploads"))
    monkeypatch.setattr(registry, "MODELS_ROOT", tmp_path / "models")
    yield
