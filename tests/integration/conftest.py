"""Isolation for integration tests that upload research datasets or train
models to disk (test_external_dataset_integration.py): redirect those
writes to a temp dir so the repo's data/ and models/ trees are untouched.

Only tests that request ``isolate_research_artifacts`` get it — this is NOT
autouse, so the rest of the integration suite (which reads the real
baseline models via the model registry) is unaffected.
"""
import pytest

import ml.pipeline.registry as registry
from app.core.config import get_settings


@pytest.fixture()
def isolate_research_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_data_path", str(tmp_path / "research_uploads"))
    monkeypatch.setattr(registry, "MODELS_ROOT", tmp_path / "models")
    yield
