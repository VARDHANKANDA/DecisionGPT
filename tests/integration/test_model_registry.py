from app.services import model_registry_service


def test_sync_from_file_registry_reads_real_manifests(db_session):
    synced = model_registry_service.sync_from_file_registry(db_session)

    # Exercises the real models/registry_index.jsonl produced by
    # `python -m ml.training.train_forecasting` / `train_churn` — if that
    # file is missing, run those scripts first.
    assert len(synced) >= 6
    model_names = {m.model_name for m in synced}
    assert "sales_forecast_xgboost" in model_names
    assert "churn_xgboost" in model_names

    xgb = model_registry_service.get_active_model(db_session, "sales_forecast_xgboost")
    assert xgb is not None
    assert xgb.status == "active"
    assert "mae" in xgb.metrics_json
    assert xgb.metrics_json["mae"] > 0
