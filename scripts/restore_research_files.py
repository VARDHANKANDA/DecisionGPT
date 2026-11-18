import shutil
from pathlib import Path

root = Path("d:/Capstone Project")
archive_research = root / "_LOCAL_ARCHIVE_NOT_FOR_GITHUB" / "research_experiments"

# 1. Restore experiments directory
src_experiments = archive_research / "experiments"
dst_experiments = root / "experiments"
if src_experiments.exists():
    print(f"Restoring experiments from {src_experiments} to {dst_experiments}...")
    shutil.copytree(src_experiments, dst_experiments, dirs_exist_ok=True)
    print("Done. Count of files in experiments:", len(list(dst_experiments.rglob("*"))))

# 2. Restore data/external
src_external = archive_research / "data_external"
dst_external = root / "data" / "external"
if src_external.exists():
    print(f"Restoring data/external from {src_external} to {dst_external}...")
    shutil.copytree(src_external, dst_external, dirs_exist_ok=True)
    print("Done. Count of files in data/external:", len(list(dst_external.rglob("*"))))

# 3. Restore data/research_uploads
src_uploads = archive_research / "data_research_uploads"
dst_uploads = root / "data" / "research_uploads"
if src_uploads.exists():
    print(f"Restoring data/research_uploads from {src_uploads} to {dst_uploads}...")
    shutil.copytree(src_uploads, dst_uploads, dirs_exist_ok=True)
    print("Done. Count of files in data/research_uploads:", len(list(dst_uploads.rglob("*"))))

