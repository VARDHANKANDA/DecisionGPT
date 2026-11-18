import pytest
import sys
from pathlib import Path

root = Path("d:/Capstone Project")
api_dir = root / "tests" / "api"
unit_dir = root / "tests" / "unit"

test_files = []
for p in api_dir.glob("test_research_*.py"):
    test_files.append(str(p))
for p in api_dir.glob("test_evaluation_*.py"):
    test_files.append(str(p))
test_files.append(str(api_dir / "test_llm_evaluation_status.py"))
test_files.append(str(api_dir / "test_model_evaluation_summary.py"))

print(f"Running pytest on {len(test_files)} test files:")
for f in test_files:
    print(" ", Path(f).name)

exit_code = pytest.main(["-q", "--tb=short"] + test_files)
print(f"\nPytest finished with exit code: {exit_code}")
sys.exit(exit_code)

