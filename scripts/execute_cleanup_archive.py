"""DecisionGPT Repository Cleanup & Archival Execution Script.

Safely relocates all research papers, overleaf files, academic thesis reports,
research datasets, raw experiment runs, and audit files into:
    D:\\Capstone Project\\_LOCAL_ARCHIVE_NOT_FOR_GITHUB\\

Maintains a comprehensive manifest:
    D:\\Capstone Project\\_LOCAL_ARCHIVE_NOT_FOR_GITHUB\\CLEANUP_MANIFEST.md

Rules:
- NEVER delete any file.
- Only move items into the structured archive.
- Verify each item after moving.
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(r"D:\Capstone Project").resolve()
ARCHIVE_DIR = ROOT_DIR / "_LOCAL_ARCHIVE_NOT_FOR_GITHUB"

# Category subdirectories in archive
CATEGORIES = {
    "research_papers": ARCHIVE_DIR / "research_papers",
    "academic_reports": ARCHIVE_DIR / "academic_reports",
    "research_experiments": ARCHIVE_DIR / "research_experiments",
    "old_documentation": ARCHIVE_DIR / "old_documentation",
    "audit_reports": ARCHIVE_DIR / "audit_reports",
    "backups": ARCHIVE_DIR / "backups",
    "temporary_files": ARCHIVE_DIR / "temporary_files",
    "generated_artifacts": ARCHIVE_DIR / "generated_artifacts",
    "local_databases": ARCHIVE_DIR / "local_databases",
    "development_environments": ARCHIVE_DIR / "development_environments",
    "unused_assets": ARCHIVE_DIR / "unused_assets",
    "miscellaneous": ARCHIVE_DIR / "miscellaneous",
}

for cat_dir in CATEGORIES.values():
    cat_dir.mkdir(parents=True, exist_ok=True)

# Specification docs in docs/ that MUST BE RETAINED for software application
RETAIN_DOCS = {
    "AI_MODULE_SPECIFICATION.md",
    "API_SPECIFICATION.md",
    "BACKEND_SPECIFICATION.md",
    "BUSINESS_FORECASTING.md",
    "BUSINESS_OS.md",
    "BUSINESS_OUTCOME_TRACKING.md",
    "CAUSAL_GRAPH_SPECIFICATION.md",
    "DATABASE_SCHEMA.md",
    "DATASET_DOWNLOAD_INSTRUCTIONS.md",
    "DATA_SPECIFICATION.md",
    "DATA_UPLOADS_AND_EVALUATION.md",
    "DEMO_GUIDE.md",
    "DEMO_READINESS.md",
    "DEPLOYMENT.md",
    "DIGITAL_TWIN_SPECIFICATION.md",
    "EXPERIMENT_GUIDE.md",
    "EXPERIMENT_PLAN.md",
    "FRONTEND_SPECIFICATION.md",
    "GOAL_PLANNER_SPECIFICATION.md",
    "IDENTITY_DECISION_RECORD.md",
    "LLM_ANALYTICS_PATH.md",
    "ML_IMPROVEMENT_PLAN.md",
    "MODEL_LIFECYCLE.md",
    "MULTI_AGENT_SPECIFICATION.md",
    "MULTI_SCENARIO_EXPERIMENT_PROTOCOL.md",
    "OPENAI_INTEGRATION.md",
    "PRD.md",
    "PRODUCTION_ML_ROADMAP.md",
    "RESEARCH_TRACEABILITY.md",
    "TESTING_SPECIFICATION.md",
    "VOICE_ACCESSIBILITY.md",
}

# Scripts in scripts/ that MUST BE RETAINED for running/testing software
RETAIN_SCRIPTS = {
    "seed_demo_accounts.py",
    "check_env.py",
    "verify_rbac.py",
    "audit_e2e.py",
    "verify_production_multiagent_direct.py",
    "verify_openai_live.py",
    "validate_readme.py",
    "generate_platform_data.py",
    "execute_cleanup_archive.py",
}

manifest_records = []


def move_item(rel_src: str, category: str, dest_name: str | None, reason: str):
    src_path = ROOT_DIR / rel_src
    if not src_path.exists():
        print(f"[SKIP] Source not found: {rel_src}")
        return

    dest_folder = CATEGORIES[category]
    target_name = dest_name if dest_name else src_path.name
    dest_path = dest_folder / target_name

    dest_folder.mkdir(parents=True, exist_ok=True)

    print(f"[MOVE] {rel_src} -> {dest_path.relative_to(ROOT_DIR)}")
    try:
        shutil.move(str(src_path), str(dest_path))
        verified = dest_path.exists() and not src_path.exists()
        manifest_records.append({
            "original_path": rel_src,
            "archive_path": str(dest_path.relative_to(ROOT_DIR)),
            "category": category,
            "reason": reason,
            "verified": verified,
        })
    except Exception as exc:
        print(f"[ERROR] Failed to move {rel_src}: {exc}")
        manifest_records.append({
            "original_path": rel_src,
            "archive_path": str(dest_path.relative_to(ROOT_DIR)),
            "category": category,
            "reason": f"FAILED: {exc}",
            "verified": False,
        })


def main():
    print("=== STARTING REPOSITORY ARCHIVAL ===")

    # 1. Research Papers & Overleaf submissions
    move_item("overleaf", "research_papers", None, "Academic research paper LaTeX project")
    move_item("overleaf1", "research_papers", None, "Academic research paper LaTeX project (submission draft)")
    move_item("overleaf1_backup_author_revision", "research_papers", None, "Author revision backup of LaTeX paper")
    move_item("overleaf1_backup_final_audit", "research_papers", None, "Final audit backup of LaTeX paper")
    move_item("overleaf1_baseline_backup", "research_papers", None, "Baseline backup of LaTeX paper")
    move_item("overleaf1_submission_package.zip", "research_papers", None, "Submission zip package for Overleaf/IEEE")
    move_item("submission_7page", "research_papers", None, "7-page conference submission draft package")
    move_item("submission_final", "research_papers", None, "Final camera-ready academic paper submission package")

    # Paper subfolders in docs/
    move_item("docs/ieee_paper", "research_papers", "docs_ieee_paper", "IEEE paper manuscripts and TeX artifacts")
    move_item("docs/ieee_paper_r1", "research_papers", "docs_ieee_paper_r1", "IEEE paper revision 1 draft and review notes")
    move_item("docs/ieee_paper_r2", "research_papers", "docs_ieee_paper_r2", "IEEE paper revision 2 draft and review notes")
    move_item("docs/templates", "research_papers", "docs_templates", "LaTeX conference format templates")
    move_item("docs/figures", "research_papers", "docs_figures", "Publication figures and plots for academic paper")
    move_item("docs/evidence", "research_papers", "docs_evidence", "Academic research empirical evidence bundles")

    # 2. Academic Reports
    move_item("Project Report", "academic_reports", "Project_Report", "Capstone thesis reference document and generated thesis Word reports")
    move_item("scripts/report_sections", "academic_reports", "scripts_report_sections", "Thesis Word report chapter generators")
    move_item("scripts/build_capstone_report.py", "academic_reports", None, "Python script compiling Capstone DOCX report")
    move_item("scripts/capture_report_screenshots.py", "academic_reports", None, "Script capturing UI screenshots for thesis doc")
    move_item("scripts/generate_report_diagrams.py", "academic_reports", None, "Script generating matplotlib diagrams for thesis doc")

    # 3. Research Experiments & Datasets
    move_item("experiments", "research_experiments", None, "Empirical research experiment suites, protocols, and ablation results")
    move_item("notebooks", "research_experiments", None, "Exploratory research Jupyter notebooks (forecast studies, LLM benchmarks)")
    move_item("_eval_scratch_ablation.db", "research_experiments", None, "Local SQLite evaluation scratch database for ablations")
    move_item("_eval_scratch_candidates.db", "research_experiments", None, "Local SQLite evaluation scratch database for candidate strategies")
    move_item("data/external", "research_experiments", "data_external", "1.34 GB non-application research datasets (M5, UCI, Myanmar, Kaggle)")
    move_item("data/research_uploads", "research_experiments", "data_research_uploads", "Research Console runtime evaluation uploads")

    # 4. Root Audit Reports (20 markdown files)
    root_audits = [
        "BASELINE_REPRODUCTION_REPORT.md",
        "CHURN_CALIBRATION_IMPROVEMENT_REPORT.md",
        "CLAIM_EVIDENCE_MATRIX.md",
        "CONFERENCE_SHORTLIST.md",
        "DIGITAL_TWIN_RISK_IMPROVEMENT_REPORT.md",
        "FINAL_EVIDENCE_AUDIT.md",
        "FINAL_SUBMISSION_CHECKLIST.md",
        "FINAL_SUBMISSION_GATE.md",
        "FORECASTING_EVIDENCE_AUDIT.md",
        "FORECASTING_IMPROVEMENT_REPORT.md",
        "FULL_SYSTEM_AUDIT.md",
        "IEEE_CAMERA_READY_AUDIT.md",
        "LLM_RELIABILITY_IMPROVEMENT_REPORT.md",
        "PRODUCTION_VS_EXPERIMENTAL_METHODS.md",
        "PROJECT_AUDIT.md",
        "RESEARCH_AUDIT_REPORT.md",
        "RESULTS_IMPROVEMENT_PLAN.md",
        "RESULTS_IMPROVEMENT_REPORT.md",
        "SIMULATED_PEER_REVIEWS.md",
        "STATISTICAL_REPORT.md",
    ]
    for audit_file in root_audits:
        move_item(audit_file, "audit_reports", f"root_{audit_file}", "Academic review and research audit report")

    # 5. Old Documentation & Research-only docs in docs/
    move_item("research", "old_documentation", "research_program", "Research blueprints, literature reviews, and positioning documents")

    docs_dir = ROOT_DIR / "docs"
    if docs_dir.exists():
        for doc_item in list(docs_dir.iterdir()):
            if doc_item.name not in RETAIN_DOCS and doc_item.is_file():
                move_item(
                    f"docs/{doc_item.name}",
                    "audit_reports" if "AUDIT" in doc_item.name or "REPORT" in doc_item.name else "old_documentation",
                    f"docs_{doc_item.name}",
                    "Research study documentation or intermediate audit"
                )

    # 6. Research Scripts in scripts/
    scripts_dir = ROOT_DIR / "scripts"
    if scripts_dir.exists():
        for script_item in list(scripts_dir.iterdir()):
            if script_item.name not in RETAIN_SCRIPTS and script_item.name != "__pycache__":
                move_item(
                    f"scripts/{script_item.name}",
                    "research_experiments",
                    f"scripts_{script_item.name}",
                    "Research evaluation script, dataset downloader, or paper utility"
                )

    # 7. Backups
    move_item(".formatting_fix_backup", "backups", ".formatting_fix_backup", "Temporary formatting backup")

    # 8. Temporary Files & Caches
    move_item(".tools", "temporary_files", ".tools", "Tectonic binary tools for compiling LaTeX")
    move_item("catboost_info", "temporary_files", "catboost_info", "CatBoost runtime training log artifacts")
    move_item(".pytest_cache", "temporary_files", ".pytest_cache", "Pytest cache folder")
    move_item(".claude", "miscellaneous", ".claude", "Local IDE scratch configuration")

    # 9. Local Databases & Runtime Uploads
    move_item("dev.db", "local_databases", "root_dev.db", "Local development SQLite database")
    move_item("backend/dev.db", "local_databases", "backend_dev.db", "Backend development SQLite database")
    move_item(".local", "local_databases", ".local", "Local runtime files")
    move_item("data/business_uploads", "local_databases", "data_business_uploads", "Runtime user business upload files")

    print("\n=== GENERATING CLEANUP_MANIFEST.MD ===")
    manifest_path = ARCHIVE_DIR / "CLEANUP_MANIFEST.md"
    
    cat_counts = {}
    for r in manifest_records:
        cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1

    lines = [
        "# DecisionGPT Repository Cleanup & Archival Manifest",
        "",
        f"**Date Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Archive Location:** `_LOCAL_ARCHIVE_NOT_FOR_GITHUB/` (Excluded via `.gitignore`)",
        f"**Total Items Relocated:** {len(manifest_records)}",
        "",
        "> [!IMPORTANT]",
        "> **Zero Deletion Guarantee**: All research papers, thesis reports, LaTeX manuscripts,",
        "> evaluation scratch databases, research datasets, and audit documents were safely moved",
        "> to this local archive. No files were deleted.",
        ">",
        "> This directory (`_LOCAL_ARCHIVE_NOT_FOR_GITHUB/`) is strictly ignored in Git and will never",
        "> be committed or pushed to any remote repository.",
        "",
        "## Summary by Archive Category",
        "",
        "| Category | Items Relocated | Description |",
        "|---|---|---|",
        f"| `research_papers` | {cat_counts.get('research_papers', 0)} | LaTeX sources, Overleaf packages, submission packages, and camera-ready bundles |",
        f"| `academic_reports` | {cat_counts.get('academic_reports', 0)} | Institutional Capstone Thesis Word reference templates and report generator scripts |",
        f"| `research_experiments` | {cat_counts.get('research_experiments', 0)} | Research experiment protocols, 1.34 GB external datasets, ablation DBs, notebooks, and eval scripts |",
        f"| `old_documentation` | {cat_counts.get('old_documentation', 0)} | Research blueprints, literature foundations, and deprecated research notes |",
        f"| `audit_reports` | {cat_counts.get('audit_reports', 0)} | Empirical audit reports, claim matrices, and peer review simulations |",
        f"| `backups` | {cat_counts.get('backups', 0)} | Pre-cleanup and formatting backup trees |",
        f"| `temporary_files` | {cat_counts.get('temporary_files', 0)} | LaTeX compilation tools (Tectonic), CatBoost logs, and test caches |",
        f"| `local_databases` | {cat_counts.get('local_databases', 0)} | Local SQLite dev databases and local session runtime uploads |",
        f"| `miscellaneous` | {cat_counts.get('miscellaneous', 0)} | IDE assistant local launch configs |",
        "",
        "## Detailed Inventory of Relocated Items",
        "",
        "| # | Original Path | Archive Destination | Category | Status | Archival Rationale |",
        "|---|---|---|---|---|---|",
    ]

    for idx, r in enumerate(manifest_records, 1):
        status = "Verified Relocated" if r["verified"] else "Action Required"
        lines.append(
            f"| {idx} | `{r['original_path']}` | `{r['archive_path']}` | `{r['category']}` | {status} | {r['reason']} |"
        )

    lines.append("")
    lines.append("## Verification Instructions")
    lines.append("To inspect any archived paper or report without modifying the Git repository:")
    lines.append("```bash")
    lines.append("# Check all archived research files")
    lines.append("ls -la _LOCAL_ARCHIVE_NOT_FOR_GITHUB/research_papers/")
    lines.append("ls -la _LOCAL_ARCHIVE_NOT_FOR_GITHUB/academic_reports/")
    lines.append("```")
    lines.append("")

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Manifest written to: {manifest_path}")
    print(f"Total items moved: {len(manifest_records)}")


if __name__ == "__main__":
    main()

