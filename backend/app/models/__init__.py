"""Import every model module so Base.metadata is fully populated for
Alembic autogenerate and for `Base.metadata.create_all()` in tests."""
from app.models.agent import AgentEvaluation, AgentRun
from app.models.benchmark import MarketBenchmark
from app.models.business import Business
from app.models.causal import CausalEdge, CausalGraph
from app.models.customer import Customer
from app.models.decision import Decision, DecisionOutcome
from app.models.digital_twin import DigitalTwinSimulation, DigitalTwinState
from app.models.experiment import ExperimentRun
from app.models.forecast import Forecast
from app.models.goal import Goal
from app.models.ingestion_job import DataIngestionJob
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.memory import BusinessMemory
from app.models.ml_model import MLModel
from app.models.product import Product
from app.models.research import ResearchDataset, ResearchDatasetVersion, TrainingRun
from app.models.sale import Sale
from app.models.strategy import Strategy
from app.models.user import User

__all__ = [
    "ResearchDataset",
    "ResearchDatasetVersion",
    "TrainingRun",
    "User",
    "AgentEvaluation",
    "AgentRun",
    "MarketBenchmark",
    "Business",
    "CausalEdge",
    "CausalGraph",
    "Customer",
    "Decision",
    "DecisionOutcome",
    "DigitalTwinSimulation",
    "DigitalTwinState",
    "ExperimentRun",
    "Forecast",
    "Goal",
    "DataIngestionJob",
    "InventoryRecord",
    "MarketingCampaign",
    "BusinessMemory",
    "MLModel",
    "Product",
    "Sale",
    "Strategy",
]
