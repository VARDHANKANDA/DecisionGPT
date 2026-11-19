import hashlib
import json
from pathlib import Path

root = Path("d:/Capstone Project")

directories = {
    "experiments": root / "experiments",
    "data/external": root / "data" / "external",
    "data/research_uploads": root / "data" / "research_uploads",
    "research/llm_evaluation": root / "research" / "llm_evaluation",
}

print("=== VERIFYING RESTORED DIRECTORIES ===")
for name, p in directories.items():
    if p.exists():
        files = [f for f in p.rglob("*") if f.is_file()]
        print(f"  {name:25}: EXISTS | {len(files)} files")
    else:
        print(f"  {name:25}: MISSING!")

print("\n=== VERIFYING HISTORICAL HASHES ===")
hash_file = root / "experiments" / "ml_benchmark_v1" / "HISTORICAL_HASHES.json"
assert hash_file.exists(), "HISTORICAL_HASHES.json missing!"

ref = json.loads(hash_file.read_text(encoding="utf-8"))["files"]
passed = 0
failed = 0
for rel, expected_sha in ref.items():
    target = root / rel
    if not target.exists():
        print(f"  MISSING: {rel}")
        failed += 1
        continue
    actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual_sha == expected_sha:
        passed += 1
    else:
        print(f"  MISMATCH: {rel} | Expected {expected_sha[:10]}... Got {actual_sha[:10]}...")
        failed += 1

print(f"\nHASH INTEGRITY RESULT: {passed} PASSED, {failed} FAILED out of {len(ref)} historical files.")
assert failed == 0, f"{failed} files failed hash verification!"

