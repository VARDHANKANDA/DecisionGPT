"""Real Indian SME decision-outcome capture & validation — schema validation,
anonymisation / PII rejection, no synthetic records in the real table, horizon
consistency, no leakage, import -> PredictionEvaluation, Table 2 empty vs
populated state, causal-threshold preservation, traceability, production
defaults + model registry immutability.
"""
import pytest

from app.core.errors import ValidationFailedError
from app.models.decision import (
    OUTCOME_SOURCE_REAL_INDIAN_SME,
    REAL_SME_OUTCOME_CATEGORY,
    Decision,
    DecisionOutcome,
)
from app.services import real_sme_outcome_service as svc


def _good_record(**over):
    r = {
        "business_id": "SME-7F3A", "industry": "Clothing Retail",
        "state": "Maharashtra", "district": "Pune",
        "decision_date": "2026-01-06", "decision_type": "price_increase",
        "goal": "increase_profit", "strategy": "Price +5%",
        "prediction_horizon_days": 30,
        "baseline_revenue": 850000, "predicted_revenue": 905000, "actual_revenue": 872000,
        "baseline_profit": 170000, "predicted_profit": 196000, "actual_profit": 181000,
        "baseline_units": 4200, "predicted_units": 4150, "actual_units": 4090,
        "predicted_risk": 0.18, "predicted_confidence": 0.62,
        "outcome_recorded_date": "2026-02-05", "outcome_status": "partially_achieved",
        "notes": "aggregate only", "source_type": "real_indian_sme",
        "business_country": "IN", "data_consent_status": "consented",
        "anonymization_status": "anonymized", "collection_method": "sme_self_report_form",
        "collection_date": "2026-02-06",
    }
    r.update(over)
    return r


# --- validation (pure) ----------------------------------------------


def test_valid_record_passes():
    assert svc.validate_record(_good_record()) == []


def test_missing_required_fields_reported():
    errs = svc.validate_record({"business_id": "SME-1"})
    assert any("missing required field: industry" in e for e in errs)
    assert any("missing required field: source_type" in e for e in errs)


def test_synthetic_or_demo_records_are_rejected_from_the_real_table():
    for bad in ("synthetic", "demo", "unknown", ""):
        errs = svc.validate_record(_good_record(source_type=bad))
        assert any("source_type must be 'real_indian_sme'" in e for e in errs)


def test_pii_shaped_fields_and_values_are_rejected():
    errs = svc.validate_record(_good_record(owner_phone="9876543210", customer_email="a@b.com",
                                            aadhaar_no="123456789012"))
    assert any("not allowed" in e for e in errs)             # forbidden key name
    assert any("email address" in e for e in errs)
    assert any("phone number" in e for e in errs)
    assert any("Aadhaar" in e or "account number" in e for e in errs)


def test_business_id_must_be_an_anonymised_token():
    assert any("anonymised token" in e for e in svc.validate_record(_good_record(business_id="Ramesh Textiles")))
    assert any("anonymised token" in e for e in svc.validate_record(_good_record(business_id="owner@shop.in")))
    assert svc.validate_record(_good_record(business_id="SME-42_A")) == []


def test_country_and_anonymisation_and_consent_enforced():
    assert any("India" in e for e in svc.validate_record(_good_record(business_country="US")))
    assert any("anonymized" in e for e in svc.validate_record(_good_record(anonymization_status="raw")))
    assert any("consent" in e for e in svc.validate_record(_good_record(data_consent_status="no")))


def test_horizon_must_be_supported_and_consistent_with_the_outcome_window():
    assert any("prediction_horizon_days must be one of" in e
               for e in svc.validate_record(_good_record(prediction_horizon_days=45)))
    # 30-day horizon but 150-day actual window -> rejected (no silent mismatch)
    assert any("does not match the stated" in e
               for e in svc.validate_record(_good_record(outcome_recorded_date="2026-06-05")))


def test_no_leakage_outcome_before_decision_is_rejected():
    assert any("before decision_date" in e
               for e in svc.validate_record(_good_record(outcome_recorded_date="2025-12-01")))


def test_unsupported_decision_type_rejected_capability_system_preserved():
    assert any("Digital Twin can simulate" in e
               for e in svc.validate_record(_good_record(decision_type="hire_staff")))


def test_confidence_and_risk_must_be_unit_interval():
    assert any("predicted_confidence must be in [0, 1]" in e
               for e in svc.validate_record(_good_record(predicted_confidence=1.4)))


# --- import + reporting (db) --------------------------------------


def test_empty_state_when_no_real_outcomes(db_session):
    rep = svc.get_real_sme_outcome_report(db_session)
    assert rep["collection_status"] == "PENDING"
    assert rep["table_2"] == "NOT READY"
    assert rep["n_outcomes"] == 0
    assert rep["data_category"] == REAL_SME_OUTCOME_CATEGORY
    assert "No real Indian SME outcomes available" in rep["empty_state"]
    assert rep["r0_vs_r3"].startswith("NOT APPLICABLE")


def test_import_creates_anonymised_business_decision_outcome_and_evaluation(db_session):
    from app.models.business import Business
    from app.models.evaluation import PredictionEvaluation

    res = svc.import_outcome_record(db_session, _good_record())
    assert res["imported"] is True
    assert res["data_category"] == REAL_SME_OUTCOME_CATEGORY

    biz = db_session.get(Business, res["business_id"])
    assert biz.country == "IN"
    assert "Anonymised Indian SME" in biz.name
    assert "Ramesh" not in biz.name  # no owner name anywhere

    outcome = db_session.get(DecisionOutcome, res["outcome_id"])
    assert outcome.source_type == OUTCOME_SOURCE_REAL_INDIAN_SME
    assert outcome.anonymization_status == "anonymized"
    assert outcome.outcome_horizon_days == 30
    assert outcome.business_country == "IN"

    # predicted vs actual matched -> a PredictionEvaluation exists with per-target metrics
    ev = db_session.query(PredictionEvaluation).filter(
        PredictionEvaluation.outcome_id == res["outcome_id"]).first()
    assert ev is not None
    assert "revenue" in ev.metrics_json and ev.metrics_json["revenue"]["error"] is not None
    assert "profit" in ev.metrics_json and "units" in ev.metrics_json


def test_import_rejects_invalid_record_with_full_error_list(db_session):
    with pytest.raises(ValidationFailedError) as ei:
        svc.import_outcome_record(db_session, _good_record(source_type="synthetic", owner_email="x@y.co"))
    errs = ei.value.details["errors"]
    assert any("source_type must be" in e for e in errs)
    assert any("not allowed" in e for e in errs) or any("email" in e for e in errs)
    # nothing was persisted
    assert db_session.query(DecisionOutcome).count() == 0


def test_report_populated_state_is_descriptive_only_and_separated(db_session):
    svc.import_outcome_record(db_session, _good_record(business_id="SME-A", decision_date="2026-01-06",
                                                      outcome_recorded_date="2026-02-05"))
    svc.import_outcome_record(db_session, _good_record(business_id="SME-A", decision_date="2026-02-10",
                                                      outcome_recorded_date="2026-03-12", strategy="Price -5%",
                                                      decision_type="price_decrease"))
    rep = svc.get_real_sme_outcome_report(db_session)
    assert rep["n_outcomes"] == 2
    assert rep["n_businesses"] == 1                      # clustering: 2 decisions, 1 business
    assert rep["table_2"] == "NOT READY"                 # < 5
    assert rep["statistical_inference"] == "DESCRIPTIVE ONLY"
    assert rep["provenance"]["all_anonymized"] is True
    assert rep["provenance"]["all_real_source"] is True
    assert rep["provenance"]["all_india"] is True
    assert rep["digital_twin"]["revenue"]["n"] == 2
    assert "clustered" in rep["clustering_note"]


def test_causal_threshold_constant_is_not_modified(db_session):
    from app.services import causal_feedback_service
    assert causal_feedback_service.MIN_OUTCOMES_FOR_OBSERVATIONAL == 3
    assert svc._min_outcomes() == 3


def test_production_defaults_and_model_registry_unchanged(db_session):
    from app.models.ml_model import MLModel
    from app.services import model_registry_service
    from app.services.decision_service import PipelineOptions

    model_registry_service.sync_from_file_registry(db_session)
    before = {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()}

    svc.import_outcome_record(db_session, _good_record())

    opts = PipelineOptions()
    assert opts.risk_model is None and opts.risk_penalty_lambda == 1.0
    assert {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()} == before


def test_digital_twin_report_exposes_the_separated_real_sme_block(db_session):
    from app.services import digital_twin_evaluation_service as dte
    rep = dte.get_evaluation_report(db_session)
    assert "real_indian_sme" in rep
    assert rep["real_indian_sme"]["data_category"] == REAL_SME_OUTCOME_CATEGORY
    assert rep["real_indian_sme"]["table_2"] == "NOT READY"


def test_traceability_import_result_carries_ids(db_session):
    res = svc.import_outcome_record(db_session, _good_record())
    for k in ("business_id", "decision_id", "outcome_id", "source_type", "data_category"):
        assert res[k]
    d = db_session.get(Decision, res["decision_id"])
    assert d.prompt_version == "real_sme_import_v1"
    assert d.business_id == res["business_id"]
