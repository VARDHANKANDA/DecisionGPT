import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.models.business import Business
from app.services import debate_service

db = SessionLocal()
biz = db.query(Business).first()
if not biz:
    print("No business found.")
    sys.exit(0)

print(f"Testing live AI debate for business: {biz.name} ({biz.id})...")
res = debate_service.run(
    db=db,
    business_id=biz.id,
    question="Should we increase prices by 5% to improve our profit margins?",
    mode="ai_model"
)

print("AI Debate Result Status:", res.get("status"))
print("Label:", res.get("label"))
print("Headline:", res.get("headline"))
print("Executive Synthesis:", res.get("stages", {}).get("decision_brief", {}).get("executive_synthesis"))
print("LLM Metadata:", res.get("llm_metadata"))

