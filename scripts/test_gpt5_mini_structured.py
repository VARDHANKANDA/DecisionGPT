import sys
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.services.openai_client import OpenAIClient, is_reasoning_model, extract_output

client = OpenAIClient()
print("Client configured:", client.configured, "Model:", client.model)

instructions = "You are the Lead Business Analyst in DecisionGPT. Return valid JSON only with keys: analysis, recommendation, confidence."
schema = {
    "type": "object",
    "required": ["analysis", "recommendation", "confidence"],
    "additionalProperties": False,
    "properties": {
        "analysis": {"type": "string", "description": "Analysis of the business state"},
        "recommendation": {"type": "string", "description": "Actionable recommendation"},
        "confidence": {"type": "number", "description": "Confidence from 0 to 1"}
    }
}

reasoning = is_reasoning_model(client.model)
payload = {
    "model": client.model,
    "instructions": instructions,
    "input": "Sales this month: ₹1,50,000 (+12% vs prior month). Top category: Electronics (45% of sales).",
    "store": False,
    "max_output_tokens": 1500 if reasoning else 800,
    "text": {"format": {"type": "json_schema", "name": "analyst_response", "strict": True, "schema": schema}}
}
if reasoning:
    payload["reasoning"] = {"effort": "low"}

print("Calling OpenAI API with GPT-5 mini...")
resp = client._call(payload)
text, refusal = extract_output(resp)
usage = resp.get("usage", {})
cost = (usage.get("input_tokens", 0) * 0.25 + usage.get("output_tokens", 0) * 2.00) / 1e6

print("Response text:", text)
print("Usage:", usage)
print(f"Estimated Cost: ${cost:.6f}")
print("Response model:", resp.get("model"))

