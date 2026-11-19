import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.models.business import Business
from app.services import agent_consult_service

db = SessionLocal()
biz = db.query(Business).first()

print("Testing consult_agent for financial-advisor...")
res = agent_consult_service.consult_agent(
    db=db,
    business_id=biz.id,
    agent_id="financial-advisor",
    task="Evaluate our margin sustainability if supplier costs increase by 10%."
)

print("Agent Name:", res.get("agent_name"))
print("Executive Summary:", res.get("executive_summary"))
print("Key Findings:", res.get("key_findings"))
print("Recommended Actions:", res.get("recommended_actions"))
print("LLM Metadata:", res.get("llm_metadata"))

