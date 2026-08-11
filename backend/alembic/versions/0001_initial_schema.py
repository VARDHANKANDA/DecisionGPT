"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-11

Generated from app/models/*.py (Base.metadata) via
scripts/_gen_initial_migration.py so the migration and the ORM models can
never silently drift apart for the initial schema.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("business_type", sa.String(100), nullable=False),
        sa.Column("business_size", sa.String(50), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "experiment_runs",
        sa.Column("experiment_name", sa.String(255), nullable=False),
        sa.Column("experiment_type", sa.String(50), nullable=False),
        sa.Column("dataset_version", sa.String(50)),
        sa.Column("model_version", sa.String(50)),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("result_path", sa.String(500)),
        sa.Column("random_seed", sa.Integer()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_experiment_runs_experiment_type", "experiment_runs", ["experiment_type"])
    op.create_index("ix_experiment_runs_status", "experiment_runs", ["status"])

    op.create_table(
        "market_benchmarks",
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("business_size", sa.String(50), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("median_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("lower_quartile", sa.Numeric(14, 4)),
        sa.Column("upper_quartile", sa.Numeric(14, 4)),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("evidence_level", sa.String(30), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_market_benchmarks_industry", "market_benchmarks", ["industry"])
    op.create_index("ix_market_benchmarks_metric", "market_benchmarks", ["metric"])

    op.create_table(
        "models",
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("dataset_version", sa.String(50), nullable=False),
        sa.Column("feature_version", sa.String(50), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("model_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_models_model_type", "models", ["model_type"])
    op.create_index("ix_models_model_name", "models", ["model_name"])
    op.create_index("ix_models_status", "models", ["status"])

    op.create_table(
        "business_memory",
        sa.Column("memory_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_business_memory_business_id", "business_memory", ["business_id"])
    op.create_index("ix_business_memory_memory_type", "business_memory", ["memory_type"])

    op.create_table(
        "causal_graphs",
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("graph_json", sa.JSON(), nullable=False),
        sa.Column("method", sa.String(100), nullable=False),
        sa.Column("evidence_summary", sa.Text()),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_causal_graphs_business_id", "causal_graphs", ["business_id"])

    op.create_table(
        "customers",
        sa.Column("external_customer_id", sa.String(100)),
        sa.Column("segment", sa.String(100)),
        sa.Column("first_purchase_date", sa.Date()),
        sa.Column("last_purchase_date", sa.Date()),
        sa.Column("purchase_frequency", sa.Numeric(10, 2)),
        sa.Column("monetary_value", sa.Numeric(14, 2)),
        sa.Column("churn_probability", sa.Numeric(5, 4)),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customers_business_id", "customers", ["business_id"])
    op.create_index("ix_customers_external_customer_id", "customers", ["external_customer_id"])

    op.create_table(
        "forecasts",
        sa.Column("model_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("models.id", ondelete="SET NULL"), nullable=False),
        sa.Column("forecast_type", sa.String(50), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("predicted_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("lower_bound", sa.Numeric(14, 4)),
        sa.Column("upper_bound", sa.Numeric(14, 4)),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forecasts_forecast_date", "forecasts", ["forecast_date"])
    op.create_index("ix_forecasts_model_id", "forecasts", ["model_id"])
    op.create_index("ix_forecasts_business_id", "forecasts", ["business_id"])

    op.create_table(
        "goals",
        sa.Column("objective", sa.String(100), nullable=False),
        sa.Column("target_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("target_unit", sa.String(20), nullable=False),
        sa.Column("primary_kpi", sa.String(50), nullable=False),
        sa.Column("time_horizon", sa.Integer()),
        sa.Column("constraints_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goals_business_id", "goals", ["business_id"])
    op.create_index("ix_goals_status", "goals", ["status"])

    op.create_table(
        "marketing_campaigns",
        sa.Column("campaign_date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("campaign_name", sa.String(255)),
        sa.Column("spend", sa.Numeric(14, 2), nullable=False),
        sa.Column("impressions", sa.Integer()),
        sa.Column("clicks", sa.Integer()),
        sa.Column("conversions", sa.Integer()),
        sa.Column("attributed_revenue", sa.Numeric(14, 2)),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_marketing_campaigns_business_id", "marketing_campaigns", ["business_id"])
    op.create_index("ix_marketing_campaigns_campaign_date", "marketing_campaigns", ["campaign_date"])

    op.create_table(
        "products",
        sa.Column("external_product_id", sa.String(100)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("unit_cost", sa.Numeric(12, 2)),
        sa.Column("selling_price", sa.Numeric(12, 2)),
        sa.Column("stock_quantity", sa.Integer()),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_external_product_id", "products", ["external_product_id"])
    op.create_index("ix_products_business_id", "products", ["business_id"])

    op.create_table(
        "causal_edges",
        sa.Column("causal_graph_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("causal_graphs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node", sa.String(100), nullable=False),
        sa.Column("target_node", sa.String(100), nullable=False),
        sa.Column("relationship", sa.String(20), nullable=False),
        sa.Column("strength", sa.Numeric(6, 4)),
        sa.Column("confidence", sa.Numeric(6, 4)),
        sa.Column("evidence_type", sa.String(30), nullable=False),
        sa.Column("time_lag", sa.Integer()),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_causal_edges_causal_graph_id", "causal_edges", ["causal_graph_id"])

    op.create_table(
        "digital_twin_states",
        sa.Column("goal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("goals.id", ondelete="CASCADE")),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_digital_twin_states_business_id", "digital_twin_states", ["business_id"])
    op.create_index("ix_digital_twin_states_goal_id", "digital_twin_states", ["goal_id"])

    op.create_table(
        "inventory",
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("stock_level", sa.Integer(), nullable=False),
        sa.Column("reorder_level", sa.Integer()),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_product_id", "inventory", ["product_id"])
    op.create_index("ix_inventory_date", "inventory", ["date"])
    op.create_index("ix_inventory_business_id", "inventory", ["business_id"])

    op.create_table(
        "sales",
        sa.Column("customer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("customers.id", ondelete="SET NULL")),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("revenue", sa.Numeric(14, 2), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sales_business_id", "sales", ["business_id"])
    op.create_index("ix_sales_sale_date", "sales", ["sale_date"])
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])
    op.create_index("ix_sales_product_id", "sales", ["product_id"])

    op.create_table(
        "strategies",
        sa.Column("goal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_strategies_business_id", "strategies", ["business_id"])
    op.create_index("ix_strategies_goal_id", "strategies", ["goal_id"])

    op.create_table(
        "agent_evaluations",
        sa.Column("strategy_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("evaluation_json", sa.JSON(), nullable=False),
        sa.Column("score", sa.Numeric(6, 4)),
        sa.Column("model_name", sa.String(100)),
        sa.Column("prompt_version", sa.String(50)),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_evaluations_agent_name", "agent_evaluations", ["agent_name"])
    op.create_index("ix_agent_evaluations_strategy_id", "agent_evaluations", ["strategy_id"])

    op.create_table(
        "decisions",
        sa.Column("goal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_strategy_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("strategies.id", ondelete="SET NULL")),
        sa.Column("expected_outcome_json", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4)),
        sa.Column("reasoning", sa.Text()),
        sa.Column("causal_graph_version", sa.String(50)),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_decisions_business_id", "decisions", ["business_id"])
    op.create_index("ix_decisions_goal_id", "decisions", ["goal_id"])

    op.create_table(
        "digital_twin_simulations",
        sa.Column("goal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("goals.id", ondelete="CASCADE")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("strategies.id", ondelete="CASCADE")),
        sa.Column("input_state_json", sa.JSON(), nullable=False),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("output_state_json", sa.JSON(), nullable=False),
        sa.Column("risk_score", sa.Numeric(6, 4)),
        sa.Column("model_version", sa.String(50)),
        sa.Column("graph_version", sa.String(50)),
        sa.Column("assumptions_json", sa.JSON(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_digital_twin_simulations_goal_id", "digital_twin_simulations", ["goal_id"])
    op.create_index("ix_digital_twin_simulations_business_id", "digital_twin_simulations", ["business_id"])
    op.create_index("ix_digital_twin_simulations_strategy_id", "digital_twin_simulations", ["strategy_id"])

    op.create_table(
        "agent_runs",
        sa.Column("decision_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("decisions.id", ondelete="CASCADE")),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100)),
        sa.Column("prompt_version", sa.String(50)),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_runs_business_id", "agent_runs", ["business_id"])
    op.create_index("ix_agent_runs_agent_name", "agent_runs", ["agent_name"])
    op.create_index("ix_agent_runs_decision_id", "agent_runs", ["decision_id"])

    op.create_table(
        "decision_outcomes",
        sa.Column("decision_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actual_outcome_json", sa.JSON(), nullable=False),
        sa.Column("goal_achieved", sa.Boolean()),
        sa.Column("goal_achievement_score", sa.Numeric(6, 4)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    )
    op.create_index("ix_decision_outcomes_decision_id", "decision_outcomes", ["decision_id"])


def downgrade() -> None:
    # Reverse dependency order.
    op.drop_table("decision_outcomes")
    op.drop_table("agent_runs")
    op.drop_table("digital_twin_simulations")
    op.drop_table("decisions")
    op.drop_table("agent_evaluations")
    op.drop_table("strategies")
    op.drop_table("sales")
    op.drop_table("inventory")
    op.drop_table("digital_twin_states")
    op.drop_table("causal_edges")
    op.drop_table("products")
    op.drop_table("marketing_campaigns")
    op.drop_table("goals")
    op.drop_table("forecasts")
    op.drop_table("customers")
    op.drop_table("causal_graphs")
    op.drop_table("business_memory")
    op.drop_table("models")
    op.drop_table("market_benchmarks")
    op.drop_table("experiment_runs")
    op.drop_table("businesses")
