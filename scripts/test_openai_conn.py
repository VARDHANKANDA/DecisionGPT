import os
import sys

# Ensure backend is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import get_settings
from app.services.openai_client import OpenAIClient

s = get_settings()
print(f"Configured API Key present: {bool(s.openai_api_key)}")
print(f"Configured Model: {s.openai_model}")

client = OpenAIClient()
print(f"OpenAIClient configured: {client.configured}")

res = client.explain(
    question="What is our total sales revenue?",
    facts=["Total sales revenue for the month is 50,000 INR."],
    notes=[]
)
print("Explain Result:")
print("  ok:", res.ok)
print("  error:", res.error)
print("  text:", res.text)
print("  model:", res.model)
print("  response_model:", res.response_model)
print("  usage:", res.usage)
print("  latency_s:", res.latency_s)

