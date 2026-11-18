"""
Generate clean, publication-grade architecture, workflow, and relational diagrams for DecisionGPT.
Eliminates all overlapping text, collided labels, crossed lines, and cramped elements.
Uses professional color palettes (slate, navy, muted blue, off-white) and crisp typography.
Saves 300 DPI PNGs to Project Report/Final_Diagrams/ and Project Report/Figures/.
"""

import os
import shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FINAL_DIAGRAMS_DIR = os.path.join(ROOT_DIR, "Project Report", "Final_Diagrams")
FIGURES_DIR = os.path.join(ROOT_DIR, "Project Report", "Figures")

os.makedirs(FINAL_DIAGRAMS_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

# Set global matplotlib font settings
plt.rcParams['font.sans-serif'] = ['Arial', 'Segoe UI', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'

# Professional Color Palette
C_NAVY_DARK = "#0f172a"
C_NAVY = "#1e293b"
C_SLATE = "#334155"
C_MUTED = "#64748b"
C_LIGHT_BG = "#f8fafc"
C_WHITE = "#ffffff"
C_BORDER_GRAY = "#cbd5e1"

C_BLUE_BORDER = "#2563eb"
C_BLUE_BG = "#eff6ff"
C_BLUE_TEXT = "#1d4ed8"

C_GREEN_BORDER = "#16a34a"
C_GREEN_BG = "#f0fdf4"
C_GREEN_TEXT = "#15803d"

C_PURPLE_BORDER = "#7c3aed"
C_PURPLE_BG = "#faf5ff"
C_PURPLE_TEXT = "#6d28d9"

C_AMBER_BORDER = "#d97706"
C_AMBER_BG = "#fffbeb"
C_AMBER_TEXT = "#b45309"

C_CYAN_BORDER = "#0891b2"
C_CYAN_BG = "#ecfeff"
C_CYAN_TEXT = "#0e7490"

def save_and_sync(fig, filename):
    plt.tight_layout()
    p1 = os.path.join(FINAL_DIAGRAMS_DIR, filename)
    p2 = os.path.join(FIGURES_DIR, filename)
    fig.savefig(p1, dpi=300, bbox_inches='tight', pad_inches=0.15)
    fig.savefig(p2, dpi=300, bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)
    print(f"  [SAVED] {filename} (300 DPI) -> Final_Diagrams & Figures")

def draw_card(ax, x, y, w, h, title=None, subtitle=None, details=None,
              bg=C_WHITE, border=C_BORDER_GRAY, lw=1.2, r=1.5,
              title_color=C_NAVY, title_size=9.5, sub_size=8.0, det_size=7.5,
              align="center"):
    box = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                         linewidth=lw, edgecolor=border, facecolor=bg)
    ax.add_patch(box)
    
    if title and not subtitle and not details:
        ax.text(x + w/2, y + h/2, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold", color=title_color)
    elif title and subtitle and not details:
        ax.text(x + w/2, y + h*0.64, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold", color=title_color)
        ax.text(x + w/2, y + h*0.30, subtitle, ha="center", va="center",
                fontsize=sub_size, color=C_MUTED)
    elif title and details:
        # Card with header bar or structured text
        ax.text(x + w/2, y + h - 2.5, title, ha="center", va="top",
                fontsize=title_size, fontweight="bold", color=title_color)
        if subtitle:
            ax.text(x + w/2, y + h - 5.5, subtitle, ha="center", va="top",
                    fontsize=sub_size, fontstyle="italic", color=C_MUTED)
            det_y = y + h - 8.5
        else:
            det_y = y + h - 5.5
            
        if isinstance(details, list):
            for i, line in enumerate(details):
                cur_y = det_y - i * 3.2
                if align == "left":
                    ax.text(x + 2.0, cur_y, line, ha="left", va="top",
                            fontsize=det_size, color=C_SLATE)
                else:
                    ax.text(x + w/2, cur_y, line, ha="center", va="top",
                            fontsize=det_size, color=C_SLATE)
        elif isinstance(details, str):
            ax.text(x + w/2, det_y, details, ha="center", va="top",
                    fontsize=det_size, color=C_SLATE)

def draw_conn(ax, x1, y1, x2, y2, label=None, color=C_SLATE, lw=1.2, style="->", rad=0.0):
    connectionstyle = f"arc3,rad={rad}" if rad != 0 else "arc3"
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle=style, color=color, lw=lw,
            shrinkA=3, shrinkB=3, mutation_scale=10,
            connectionstyle=connectionstyle
        )
    )
    if label:
        lx = (x1 + x2) / 2
        ly = (y1 + y2) / 2
        ax.text(lx, ly, label, ha="center", va="center", fontsize=7.0,
                fontweight="semibold", color=C_NAVY,
                bbox=dict(boxstyle="square,pad=0.2", fc=C_WHITE, ec="none", alpha=0.9))


# ==============================================================================
# 1. FIGURE 3.1: UML USE CASE DIAGRAM (figure_use_case.png)
# ==============================================================================
def generate_figure_3_1():
    print("Generating Figure 3.1: Use Case Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Title
    ax.text(50, 96.5, "DECISIONGPT SYSTEM USE-CASE SPECIFICATION", ha="center",
            fontsize=12, fontweight="bold", color=C_NAVY_DARK)

    # Left Actors Box
    draw_card(ax, 3, 56, 22, 36, bg=C_LIGHT_BG, border=C_SLATE, lw=1.5, r=2)
    ax.text(14, 88, "ACTOR: Business Owner", ha="center", fontsize=9.0, fontweight="bold", color=C_NAVY_DARK)
    ax.text(14, 84, "(Executive Decision Maker)", ha="center", fontsize=7.5, fontstyle="italic", color=C_MUTED)
    bo_details = [
        "• Sets strategic goals & horizons",
        "• Reviews executive KPI summary",
        "• Evaluates multi-agent trade-offs",
        "• Approves & commits decisions"
    ]
    for i, line in enumerate(bo_details):
        ax.text(4.5, 78 - i*4.2, line, ha="left", fontsize=7.2, color=C_SLATE)

    draw_card(ax, 3, 8, 22, 44, bg=C_LIGHT_BG, border=C_SLATE, lw=1.5, r=2)
    ax.text(14, 48, "ACTOR: Financial Analyst", ha="center", fontsize=9.0, fontweight="bold", color=C_NAVY_DARK)
    ax.text(14, 44, "(Financial Planning & Strategy)", ha="center", fontsize=7.5, fontstyle="italic", color=C_MUTED)
    fa_details = [
        "• Inspects gross margin momentum",
        "• Tracks cash runway & burn rate",
        "• Simulates price/cost shocks",
        "• Validates insolvency ruin risks",
        "• Performs scenario comparisons"
    ]
    for i, line in enumerate(fa_details):
        ax.text(4.5, 38 - i*4.2, line, ha="left", fontsize=7.2, color=C_SLATE)

    # Right Actors Box
    draw_card(ax, 75, 56, 22, 36, bg=C_LIGHT_BG, border=C_SLATE, lw=1.5, r=2)
    ax.text(86, 88, "ACTOR: Operations Manager", ha="center", fontsize=9.0, fontweight="bold", color=C_NAVY_DARK)
    ax.text(86, 84, "(Supply Chain & Sales)", ha="center", fontsize=7.5, fontstyle="italic", color=C_MUTED)
    om_details = [
        "• Uploads transaction datasets",
        "• Executes 5-step data hygiene",
        "• Reviews demand forecast curves",
        "• Identifies inventory stockouts"
    ]
    for i, line in enumerate(om_details):
        ax.text(76.5, 78 - i*4.2, line, ha="left", fontsize=7.2, color=C_SLATE)

    draw_card(ax, 75, 8, 22, 44, bg=C_LIGHT_BG, border=C_SLATE, lw=1.5, r=2)
    ax.text(86, 48, "ACTOR: System Administrator", ha="center", fontsize=9.0, fontweight="bold", color=C_NAVY_DARK)
    ax.text(86, 44, "(Security & Governance)", ha="center", fontsize=7.5, fontstyle="italic", color=C_MUTED)
    sa_details = [
        "• Manages tenant onboarding",
        "• Configures RBAC permissions",
        "• Monitors system API health",
        "• Inspects audit traceability logs",
        "• Manages database backups"
    ]
    for i, line in enumerate(sa_details):
        ax.text(76.5, 38 - i*4.2, line, ha="left", fontsize=7.2, color=C_SLATE)

    # Center Platform Boundary
    box_plat = FancyBboxPatch((28, 5), 44, 88, boxstyle="round,pad=0,rounding_size=2",
                              linewidth=1.8, edgecolor=C_BLUE_BORDER, facecolor="#f8fafc", linestyle="--")
    ax.add_patch(box_plat)
    ax.text(50, 90.5, "DECISIONGPT PLATFORM BOUNDARY", ha="center",
            fontsize=9.5, fontweight="bold", color=C_BLUE_TEXT)

    # Use Cases (UC1 to UC7)
    use_cases = [
        ("UC1: Upload & Clean Tabular Data", "Automated 5-step canonical schema & IQR outlier hygiene", 78, C_BLUE_BG, C_BLUE_BORDER),
        ("UC2: Query Conversational Assistant", "Natural language business Q&A with strict SQL factual check", 66, C_CYAN_BG, C_CYAN_BORDER),
        ("UC3: Multi-Horizon Demand Forecasting", "1D/14D/28D GBDT regression models (HGB, RF, XGBoost)", 54, C_GREEN_BG, C_GREEN_BORDER),
        ("UC4: Causal What-If Digital Twin Simulation", "Discrete-event state-space simulation & cash runway testing", 42, C_PURPLE_BG, C_PURPLE_BORDER),
        ("UC5: Conduct Multi-Agent Swarm Debate", "7-stage dialectical deliberation across 5 specialist agents", 30, C_AMBER_BG, C_AMBER_BORDER),
        ("UC6: Commit Strategic Decision & Log Audit", "Human-in-the-loop sign-off & research provenance tracking", 18, C_BLUE_BG, C_BLUE_BORDER),
        ("UC7: Manage RBAC & Multi-Tenant Security", "Tenant-scoped database isolation and API access governance", 7, C_LIGHT_BG, C_SLATE),
    ]

    for uc_title, uc_desc, uc_y, uc_bg, uc_bc in use_cases:
        draw_card(ax, 30.5, uc_y, 39, 9.5, title=uc_title, subtitle=uc_desc,
                  bg=uc_bg, border=uc_bc, lw=1.2, r=3,
                  title_size=8.5, sub_size=6.8, title_color=C_NAVY_DARK)

    # Connectors: Left Actors to Use Cases
    # Business Owner (y=74) -> UC2, UC5, UC6
    draw_conn(ax, 25, 76, 30.5, 70, color=C_SLATE, lw=1.1)
    draw_conn(ax, 25, 73, 30.5, 35, color=C_SLATE, lw=1.1)
    draw_conn(ax, 25, 70, 30.5, 23, color=C_SLATE, lw=1.1)

    # Financial Analyst (y=30) -> UC2, UC3, UC4, UC5
    draw_conn(ax, 25, 36, 30.5, 68, color=C_SLATE, lw=1.1)
    draw_conn(ax, 25, 32, 30.5, 59, color=C_SLATE, lw=1.1)
    draw_conn(ax, 25, 28, 30.5, 47, color=C_SLATE, lw=1.1)
    draw_conn(ax, 25, 24, 30.5, 33, color=C_SLATE, lw=1.1)

    # Operations Manager (y=74) -> UC1, UC3, UC5
    draw_conn(ax, 75, 76, 69.5, 82, color=C_SLATE, lw=1.1)
    draw_conn(ax, 75, 72, 69.5, 58, color=C_SLATE, lw=1.1)
    draw_conn(ax, 75, 68, 69.5, 36, color=C_SLATE, lw=1.1)

    # System Administrator (y=30) -> UC1, UC6, UC7
    draw_conn(ax, 75, 32, 69.5, 80, color=C_SLATE, lw=1.1)
    draw_conn(ax, 75, 28, 69.5, 22, color=C_SLATE, lw=1.1)
    draw_conn(ax, 75, 24, 69.5, 12, color=C_SLATE, lw=1.1)

    save_and_sync(fig, "figure_use_case.png")


# ==============================================================================
# 2. FIGURE 4.1: OVERALL SYSTEM ARCHITECTURE (figure_overall_architecture.png)
# ==============================================================================
def generate_figure_4_1():
    print("Generating Figure 4.1: Overall Dual-Plane Architecture Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 6.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 97, "DECISIONGPT DUAL-PLANE SYSTEM ARCHITECTURE", ha="center",
            fontsize=12, fontweight="bold", color=C_NAVY_DARK)
    ax.text(50, 93.8, "Rigorous Decoupling of Deterministic Math Execution and Multi-Agent Cognitive Reasoning",
            ha="center", fontsize=8.2, fontstyle="italic", color=C_MUTED)

    # Client Presentation Tier (Top)
    draw_card(ax, 5, 80, 90, 11, bg=C_LIGHT_BG, border=C_BLUE_BORDER, lw=1.5, r=2)
    ax.text(50, 88.5, "PRESENTATION TIER (Next.js 14 · React 19 · TypeScript · Tailwind CSS · Recharts)",
            ha="center", fontsize=8.8, fontweight="bold", color=C_BLUE_TEXT)
    client_modules = [
        ("Executive Dashboard", 7, 81.5, 16),
        ("Dataset Hygiene Studio", 25, 81.5, 16),
        ("Agent Consult Arena", 43, 81.5, 16),
        ("7-Stage Debate Swarm", 61, 81.5, 16),
        ("Scenario Twin Simulator", 79, 81.5, 14.5)
    ]
    for m_title, mx, my, mw in client_modules:
        draw_card(ax, mx, my, mw, 5.5, title=m_title, bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5, title_size=7.2)

    draw_conn(ax, 50, 80, 50, 75, "HTTPS / TLS 1.3 · REST API · JWT Bearer Auth", lw=1.2)

    # DUAL-PLANE CONTAINERS
    # Left: Quantitative Mathematical Execution Plane (Deterministic)
    box_math = FancyBboxPatch((5, 22), 43, 53, boxstyle="round,pad=0,rounding_size=2",
                              linewidth=1.8, edgecolor=C_GREEN_BORDER, facecolor="#f0fdf4")
    ax.add_patch(box_math)
    ax.text(26.5, 71.5, "QUANTITATIVE MATHEMATICAL EXECUTION PLANE", ha="center",
            fontsize=8.5, fontweight="bold", color=C_GREEN_TEXT)
    ax.text(26.5, 68.5, "(Deterministic · Zero-LLM · Pure Algorithmic Grounding)", ha="center",
            fontsize=7.0, fontstyle="italic", color=C_MUTED)

    math_boxes = [
        ("Canonical Data Hygiene & Preprocessing",
         ["• Median imputation for missing values", "• IQR outlier winsorization bounds", "• Datetime ISO-8601 regularization"], 55.5),
        ("Multi-Horizon Predictive Engine",
         ["• HistGradientBoosting (1-Day, WAPE 68.1%)", "• Random Forest (14-Day, WAPE 19.8%)", "• XGBoost Regressor (28-Day, WAPE 9.3%)"], 42.5),
        ("Causal Treatment & Digital Twin Core",
         ["• Do-calculus backdoor graph adjustment", "• Discrete-event cash & stock state space", "• Monte Carlo insolvency ruin simulation"], 29.5),
        ("Deterministic Downside Penalty Scoring",
         ["• S = 0.5*(S_BA + S_FA) - lambda*(1 - S_RM)", "• Preserves capital solvency near ruin margins"], 16.5)
    ]
    for b_title, b_lines, by in math_boxes:
        draw_card(ax, 6.5, by, 40, 11.5, title=b_title, details=b_lines,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.5, det_size=6.6, align="left", title_color=C_NAVY_DARK)

    # Right: Cognitive Reasoning & Governance Plane (Multi-Agent Swarm)
    box_agent = FancyBboxPatch((52, 22), 43, 53, boxstyle="round,pad=0,rounding_size=2",
                               linewidth=1.8, edgecolor=C_PURPLE_BORDER, facecolor="#faf5ff")
    ax.add_patch(box_agent)
    ax.text(73.5, 71.5, "COGNITIVE REASONING & GOVERNANCE PLANE", ha="center",
            fontsize=8.5, fontweight="bold", color=C_PURPLE_TEXT)
    ax.text(73.5, 68.5, "(Multi-Agent Swarm · Persona Evaluation · Dialectical Debate)", ha="center",
            fontsize=7.0, fontstyle="italic", color=C_MUTED)

    agent_boxes = [
        ("Specialist Domain Agent Swarm",
         ["• Business Analyst (Revenue & concentration)", "• Financial Advisor (Margin & runway)", "• Risk Manager (Tail-risk ruin penalty)", "• Marketing & Strategy Optimisers"], 55.5),
        ("7-Stage Dialectical Debate Workspace",
         ["• Stage 1-2: Question & Verified FactSheet", "• Stage 3-4: Solo Analysis & Cross-Challenges", "• Stage 5-7: Evidence Review & Executive Brief"], 42.5),
        ("Guarded Natural Language Assistant",
         ["• Closed-schema intent classification", "• Fact verification middleware (validate_explanation)", "• Rejection of ungrounded or speculative claims"], 29.5),
        ("Strategic Decision Governance & Audit",
         ["• Human-in-the-loop executive approval gate", "• Immutable traceability to models & datasets"], 16.5)
    ]
    for b_title, b_lines, by in agent_boxes:
        draw_card(ax, 53.5, by, 40, 11.5, title=b_title, details=b_lines,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.5, det_size=6.6, align="left", title_color=C_NAVY_DARK)

    # Bi-directional communication arrow across planes
    draw_conn(ax, 48, 48, 52, 48, style="<->", color=C_SLATE, lw=1.4)
    ax.text(50, 52, "Typed Data Contracts\n(FactSheets · Diffs)", ha="center", va="center",
            fontsize=6.8, fontweight="bold", color=C_NAVY,
            bbox=dict(boxstyle="square,pad=0.2", fc=C_WHITE, ec=C_BORDER_GRAY))

    # Persistence Tier (Bottom)
    draw_card(ax, 5, 2, 90, 14, bg=C_LIGHT_BG, border=C_AMBER_BORDER, lw=1.5, r=2)
    ax.text(50, 13.5, "PERSISTENCE & STORAGE TIER (Tenant Data Isolation via business_id)",
            ha="center", fontsize=8.8, fontweight="bold", color=C_AMBER_TEXT)

    p_stores = [
        ("Relational Database", "PostgreSQL / SQLite · Users, businesses, goals, decisions, agent runs", 7, 3.5, 26),
        ("Canonical Parquet Store", "Columnar snappy-compressed clean datasets scoped by tenant", 37, 3.5, 26),
        ("Research Audit Repository", "Model manifests, metrics JSON, locked seeds, evaluation logs", 67, 3.5, 26)
    ]
    for ps_title, ps_sub, psx, psy, psw in p_stores:
        draw_card(ax, psx, psy, psw, 8.5, title=ps_title, subtitle=ps_sub,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.5, sub_size=6.5, title_color=C_NAVY_DARK)

    # Connectors to persistence
    draw_conn(ax, 26.5, 22, 26.5, 16, "SQLAlchemy / Parquet I/O", lw=1.1)
    draw_conn(ax, 73.5, 22, 73.5, 16, "Decision & Audit Logging", lw=1.1)

    save_and_sync(fig, "figure_overall_architecture.png")


# ==============================================================================
# 3. FIGURE 4.2: FRONTEND-BACKEND ARCHITECTURE (figure_frontend_backend_arch.png)
# ==============================================================================
def generate_figure_4_2():
    print("Generating Figure 4.2: Frontend-Backend Architecture Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 6.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 97, "DECISIONGPT FRONTEND-BACKEND MICROSERVICES ARCHITECTURE", ha="center",
            fontsize=12, fontweight="bold", color=C_NAVY_DARK)
    ax.text(50, 93.8, "Four-Tier Enterprise Service Decomposition and Communication Protocols",
            ha="center", fontsize=8.2, fontstyle="italic", color=C_MUTED)

    # Tier 1: Presentation Layer
    draw_card(ax, 5, 73, 90, 18, bg=C_BLUE_BG, border=C_BLUE_BORDER, lw=1.5, r=2)
    ax.text(50, 88.5, "TIER 1: PRESENTATION LAYER (Next.js 14 · React 19 · TypeScript)",
            ha="center", fontsize=8.8, fontweight="bold", color=C_BLUE_TEXT)

    fe_components = [
        ("Dashboard & Navigation", ["App Router layouts", "Executive KPI cards", "Alert notifications"], 7, 74.5, 16.5),
        ("Dataset Studio", ["File upload wizard", "Preprocessing review", "Column profiling tables"], 25, 74.5, 16.5),
        ("Specialist Arena", ["5 Agent consultation UIs", "Radar performance graphs", "Diff explanations"], 43, 74.5, 16.5),
        ("Debate Workspace", ["7-Stage consensus viewer", "Cross-agent challenges", "Synthesis brief exporter"], 61, 74.5, 16.5),
        ("Digital Twin Simulator", ["What-if shock controls", "Cash trajectory curves", "Decision sign-off modal"], 79, 74.5, 14.5),
    ]
    for comp_title, comp_lines, cx, cy, cw in fe_components:
        draw_card(ax, cx, cy, cw, 12.5, title=comp_title, details=comp_lines,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.2, det_size=6.2, align="left", title_color=C_NAVY_DARK)

    draw_conn(ax, 50, 73, 50, 68, "HTTPS / TLS 1.3 · JSON REST API · SSE Streaming · JWT Bearer Token", lw=1.2)

    # Tier 2: API Gateway & Routing Layer
    draw_card(ax, 5, 52, 90, 16, bg=C_GREEN_BG, border=C_GREEN_BORDER, lw=1.5, r=2)
    ax.text(50, 65.5, "TIER 2: API GATEWAY & ROUTING LAYER (FastAPI · Pydantic v2 · Starlette)",
            ha="center", fontsize=8.8, fontweight="bold", color=C_GREEN_TEXT)

    gateways = [
        ("Auth & Tenant Router", ["/api/v1/auth/login", "JWT verification", "Tenant scoping middleware"], 7, 53.5, 16.5),
        ("Dataset Ingestion API", ["/api/v1/datasets/upload", "/api/v1/datasets/clean", "Schema validation"], 25, 53.5, 16.5),
        ("Forecast & Churn API", ["/api/v1/forecasts/run", "/api/v1/churn/predict", "WAPE & ECE metrics"], 43, 53.5, 16.5),
        ("Debate & Swarm API", ["/api/v1/debate/start", "/api/v1/agents/consult", "Asynchronous SSE streams"], 61, 53.5, 16.5),
        ("Simulation & Decision", ["/api/v1/simulation/run", "/api/v1/decisions/commit", "Audit log persistence"], 79, 53.5, 14.5),
    ]
    for gw_title, gw_lines, gx, gy, gw in gateways:
        draw_card(ax, gx, gy, gw, 11, title=gw_title, details=gw_lines,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.2, det_size=6.2, align="left", title_color=C_NAVY_DARK)

    draw_conn(ax, 50, 52, 50, 47, "Internal Asynchronous Service Dispatch", lw=1.2)

    # Tier 3: Core Domain Services Layer
    draw_card(ax, 5, 27, 90, 20, bg=C_PURPLE_BG, border=C_PURPLE_BORDER, lw=1.5, r=2)
    ax.text(50, 44.5, "TIER 3: CORE APPLICATION & INTELLIGENCE SERVICES (Python 3.11 ASGI)",
            ha="center", fontsize=8.8, fontweight="bold", color=C_PURPLE_TEXT)

    services = [
        ("Predictive Engine", ["HistGradientBoosting", "Random Forest Regressor", "XGBoost (28-day horizon)", "Rolling temporal CV"], 7, 28.5, 20),
        ("Multi-Agent Engine", ["debate_service.py", "5 Specialist personas", "Cross-challenge generator", "Evidence FactSheet compiler"], 29, 28.5, 20),
        ("Digital Twin Simulator", ["digital_twin_service.py", "Discrete-event state-space", "Inventory & order queues", "Cash runway stress tests"], 51, 28.5, 20),
        ("Governance & Audit", ["decision_service.py", "analytics_answer_service.py", "Guarded SQL verification", "Research traceability"], 73, 28.5, 20),
    ]
    for s_title, s_lines, sx, sy, sw in services:
        draw_card(ax, sx, sy, sw, 14.5, title=s_title, details=s_lines,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.2, det_size=6.2, align="left", title_color=C_NAVY_DARK)

    draw_conn(ax, 50, 27, 50, 22, "SQLAlchemy 2.0 Async Engine · Parquet Columnar Storage IO", lw=1.2)

    # Tier 4: Storage & Persistence Layer
    draw_card(ax, 5, 4, 90, 18, bg=C_AMBER_BG, border=C_AMBER_BORDER, lw=1.5, r=2)
    ax.text(50, 19.5, "TIER 4: STORAGE & PERSISTENCE LAYER (ACID Relational & Columnar Stores)",
            ha="center", fontsize=8.8, fontweight="bold", color=C_AMBER_TEXT)

    stores = [
        ("Relational DB (PostgreSQL / SQLite)",
         ["users (auth & roles)", "businesses (tenant identity)", "scenarios (simulation setups)", "agent_runs (reasoning logs)", "decisions (approval trails)"], 7, 5.5, 27),
        ("Columnar Parquet Store",
         ["Canonical clean transaction store", "Snappy compression for high IOPS", "Partitioned by business_id", "Zero cross-tenant file leakage"], 36, 5.5, 27),
        ("Model & Audit Repository",
         ["Pre-trained model artifacts", "metrics_json experiment tables", "Verified baseline checkpoints", "Reproducible seed manifests"], 65, 5.5, 28),
    ]
    for st_title, st_lines, stx, sty, stw in stores:
        draw_card(ax, stx, sty, stw, 12.5, title=st_title, details=st_lines,
                  bg=C_WHITE, border=C_BORDER_GRAY, lw=1.0, r=1.5,
                  title_size=7.2, det_size=6.2, align="left", title_color=C_NAVY_DARK)

    save_and_sync(fig, "figure_frontend_backend_arch.png")


# ==============================================================================
# 4. FIGURE 4.3: CANONICAL PREPROCESSING WORKFLOW (figure_preprocessing_workflow.png)
# ==============================================================================
def generate_figure_4_3():
    print("Generating Figure 4.3: Canonical Preprocessing Workflow Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 4.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 95, "CANONICAL 5-STAGE GUIDED DATA INGESTION & PREPROCESSING PIPELINE",
            ha="center", fontsize=11.5, fontweight="bold", color=C_NAVY_DARK)
    ax.text(50, 90.5, "Standardizing Unstructured SME Transactional Records into High-Integrity Analytical Datasets",
            ha="center", fontsize=8.0, fontstyle="italic", color=C_MUTED)

    steps = [
        ("STAGE 1", "Upload & Ingest",
         ["• Ingests CSV / Parquet", "• Validates UTF-8 encoding", "• Preserves raw file", "• Tenant quota check"], 3, C_BLUE_BG, C_BLUE_BORDER),
        ("STAGE 2", "Schema Profiling",
         ["• Infers column types", "• Detects date / amounts", "• Entity classification", "• Baseline health audit"], 22.5, C_CYAN_BG, C_CYAN_BORDER),
        ("STAGE 3", "Missing Imputation",
         ["• Numerical: Median fill", "• Categorical: Mode fill", "• Zero-fill for units sold", "• Explicit missing flags"], 42, C_GREEN_BG, C_GREEN_BORDER),
        ("STAGE 4", "Outlier Winsorization",
         ["• IQR = Q3 - Q1 formula", "• Bounds: [Q1-1.5, Q3+1.5]", "• Spurious spike clipping", "• Volume distribution fix"], 61.5, C_PURPLE_BG, C_PURPLE_BORDER),
        ("STAGE 5", "Columnar Storage",
         ["• Snappy-Parquet export", "• Scoped by business_id", "• Fast analytical queries", "• Ready for forecasting"], 81, C_AMBER_BG, C_AMBER_BORDER),
    ]

    for stage_lbl, stage_title, stage_details, sx, s_bg, s_bc in steps:
        draw_card(ax, sx, 24, 16, 62, title=f"{stage_lbl}\n{stage_title}", details=stage_details,
                  bg=s_bg, border=s_bc, lw=1.5, r=2,
                  title_size=8.0, det_size=6.8, align="left", title_color=C_NAVY_DARK)

    # Connector arrows between stages
    for i in range(len(steps) - 1):
        x1 = steps[i][3] + 16
        x2 = steps[i+1][3]
        draw_conn(ax, x1, 55, x2, 55, color=C_SLATE, lw=1.6)

    # Safety Guarantee Banner (Bottom)
    draw_card(ax, 3, 5, 94, 13, bg="#ecfdf5", border=C_GREEN_BORDER, lw=1.5, r=2)
    ax.text(50, 13.5, "INVARIANT AUDIT SAFETY GUARANTEE", ha="center",
            fontsize=8.5, fontweight="bold", color=C_GREEN_TEXT)
    ax.text(50, 9.0,
            "Raw uploaded transaction files are stored immutably in tenant isolation and never modified or overwritten directly.\n"
            "Every preprocessing transformation is logged with full parameter provenance, allowing instantaneous reversible rollback.",
            ha="center", fontsize=7.2, color=C_SLATE)

    save_and_sync(fig, "figure_preprocessing_workflow.png")


# ==============================================================================
# 5. FIGURE 4.4: MULTI-AGENT DEBATE WORKFLOW (figure_debate_workflow.png)
# ==============================================================================
def generate_figure_4_4():
    print("Generating Figure 4.4: Multi-Agent Debate Workflow Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 6.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 97, "MULTI-AGENT SWARM DIALECTICAL DEBATE & CONSENSUS PROTOCOL",
            ha="center", fontsize=11.5, fontweight="bold", color=C_NAVY_DARK)
    ax.text(50, 93.8, "7-Stage Deliberation Engine with Downside Solvency Governance (debate_service.py)",
            ha="center", fontsize=8.0, fontstyle="italic", color=C_MUTED)

    # Row 1: Stages 1, 2, 3 (Top row: left to right)
    s1_details = ["• User defines strategic goal or shock", "• e.g. Price +10%, Ad spend +20%", "• Sets target time horizon (wks)"]
    draw_card(ax, 3, 62, 28, 28, title="STAGE 1: Question Formulation", subtitle="Goal Definition & Parameter Parsing",
              details=s1_details, bg=C_BLUE_BG, border=C_BLUE_BORDER, lw=1.4, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.6, align="left", title_color=C_BLUE_TEXT)

    draw_conn(ax, 31, 76, 36, 76, lw=1.4)

    s2_details = ["• Generates deterministic FactSheet", "• Verified SQL records & cash state", "• Digital Twin baseline simulation"]
    draw_card(ax, 36, 62, 28, 28, title="STAGE 2: Verified Evidence", subtitle="Ground-Truth FactSheet Extraction",
              details=s2_details, bg=C_CYAN_BG, border=C_CYAN_BORDER, lw=1.4, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.6, align="left", title_color=C_CYAN_TEXT)

    draw_conn(ax, 64, 76, 69, 76, lw=1.4)

    s3_details = ["• 5 Specialist Agents evaluate solo", "• Business Analyst: Demand/Velocity", "• Financial Advisor: Margin/Runway", "• Risk Manager: Solvency boundary"]
    draw_card(ax, 69, 62, 28, 28, title="STAGE 3: Specialist Analyses", subtitle="Isolated Domain Perspective Formulations",
              details=s3_details, bg=C_GREEN_BG, border=C_GREEN_BORDER, lw=1.4, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.6, align="left", title_color=C_GREEN_TEXT)

    # Turn down from Row 1 to Row 2
    draw_conn(ax, 83, 62, 83, 58, lw=1.4)

    # Row 2: Stages 4, 5 (Middle row: right to left)
    s4_details = ["• Rule-based challenge matrix", "• Compares claims across agents", "• Detects growth vs. liquidity clash", "• e.g. Marketing volume vs. Risk cash"]
    draw_card(ax, 52, 29, 45, 27, title="STAGE 4: Cross-Specialist Challenges & Conflict Flagging", subtitle="Automated Inconsistency & Over-Optimism Interception",
              details=s4_details, bg=C_AMBER_BG, border=C_AMBER_BORDER, lw=1.4, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.6, align="left", title_color=C_AMBER_TEXT)

    draw_conn(ax, 52, 42.5, 47, 42.5, lw=1.4)

    s5_details = ["• Filters unverified factual claims", "• Highlights missing variables", "• Flags extrapolation boundaries", "• Separates fact from assumption"]
    draw_card(ax, 3, 29, 44, 27, title="STAGE 5: Evidence & Assumption Review", subtitle="Epistemic Filtering & Verification Audit",
              details=s5_details, bg=C_PURPLE_BG, border=C_PURPLE_BORDER, lw=1.4, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.6, align="left", title_color=C_PURPLE_TEXT)

    # Turn down from Row 2 to Row 3
    draw_conn(ax, 25, 29, 25, 25, lw=1.4)

    # Row 3: Stages 6, 7 (Bottom row: left to right)
    s6_details = [
        "• Runs Candidate Options through Digital Twin",
        "• Downside Penalty Scoring: S = 0.5*(S_BA + S_FA) - lambda*(1 - S_RM)",
        "• Balances expected revenue against tail-risk insolvency"
    ]
    draw_card(ax, 3, 2, 44, 21, title="STAGE 6: Trade-Off Synthesis & Simulation", subtitle="Downside Solvency Risk Bounding",
              details=s6_details, bg="#fef3c7", border="#d97706", lw=1.4, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.5, align="left", title_color=C_NAVY_DARK)

    draw_conn(ax, 47, 12.5, 52, 12.5, lw=1.4)

    s7_details = [
        "• Synthesizes actionable consensus recommendation",
        "• Explicit confidence score and risk sensitivity bounds",
        "• Human-in-the-loop executive sign-off gate"
    ]
    draw_card(ax, 52, 2, 45, 21, title="STAGE 7: Final Executive Decision Brief", subtitle="Governance Sign-Off & Audit Logging",
              details=s7_details, bg="#ecfdf5", border=C_GREEN_BORDER, lw=1.6, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.5, align="left", title_color=C_GREEN_TEXT)

    save_and_sync(fig, "figure_debate_workflow.png")


# ==============================================================================
# 6. FIGURE 4.5: DATABASE ER DIAGRAM (figure_database_er.png)
# ==============================================================================
def generate_figure_4_5():
    print("Generating Figure 4.5: Relational ER Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 6.8), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 97, "DECISIONGPT RELATIONAL DATABASE ENTITY-RELATIONSHIP MODEL",
            ha="center", fontsize=11.5, fontweight="bold", color=C_NAVY_DARK)
    ax.text(50, 93.8, "Multi-Tenant Data Isolation Scoped by business_id with Relational Constraints",
            ha="center", fontsize=8.0, fontstyle="italic", color=C_MUTED)

    # Tables layout: 2 rows of 3 tables
    # Row 1 (y = 52 to 90): businesses (center), users (left), datasets (right)
    # businesses (Root tenant table)
    t_biz = [
        "id: UUID [PK]",
        "name: VARCHAR(128)",
        "industry: VARCHAR(64)",
        "currency: VARCHAR(8)",
        "created_at: TIMESTAMP",
        "updated_at: TIMESTAMP"
    ]
    draw_card(ax, 36, 52, 28, 38, title="TABLE: businesses", subtitle="Enterprise Tenant Root Entity",
              details=t_biz, bg=C_LIGHT_BG, border=C_BLUE_BORDER, lw=1.6, r=2,
              title_size=8.5, sub_size=6.8, det_size=7.0, align="left", title_color=C_BLUE_TEXT)

    # users
    t_usr = [
        "id: UUID [PK]",
        "business_id: UUID [FK]",
        "email: VARCHAR(255) [UQ]",
        "hashed_password: VARCHAR",
        "role: VARCHAR(32)",
        "is_active: BOOLEAN"
    ]
    draw_card(ax, 3, 52, 28, 38, title="TABLE: users", subtitle="Authentication & RBAC Roles",
              details=t_usr, bg=C_WHITE, border=C_SLATE, lw=1.2, r=2,
              title_size=8.5, sub_size=6.8, det_size=7.0, align="left", title_color=C_NAVY_DARK)

    # datasets
    t_data = [
        "id: UUID [PK]",
        "business_id: UUID [FK]",
        "filename: VARCHAR(255)",
        "row_count: INTEGER",
        "canonical_path: VARCHAR",
        "health_score: FLOAT"
    ]
    draw_card(ax, 69, 52, 28, 38, title="TABLE: datasets", subtitle="Tabular Ingestion Metadata",
              details=t_data, bg=C_WHITE, border=C_SLATE, lw=1.2, r=2,
              title_size=8.5, sub_size=6.8, det_size=7.0, align="left", title_color=C_NAVY_DARK)

    # Connectors Row 1
    draw_conn(ax, 36, 71, 31, 71, label="1 : N", color=C_SLATE, lw=1.2)
    draw_conn(ax, 64, 71, 69, 71, label="1 : N", color=C_SLATE, lw=1.2)

    # Row 2 (y = 5 to 43): scenarios (left), agent_runs (center), decisions (right)
    # scenarios
    t_scen = [
        "id: UUID [PK]",
        "business_id: UUID [FK]",
        "name: VARCHAR(128)",
        "baseline_state: JSONB",
        "shock_params: JSONB",
        "horizon_weeks: INTEGER"
    ]
    draw_card(ax, 3, 5, 28, 38, title="TABLE: scenarios", subtitle="Simulation & Shock Setups",
              details=t_scen, bg=C_WHITE, border=C_SLATE, lw=1.2, r=2,
              title_size=8.5, sub_size=6.8, det_size=7.0, align="left", title_color=C_NAVY_DARK)

    # agent_runs
    t_runs = [
        "id: UUID [PK]",
        "business_id: UUID [FK]",
        "scenario_id: UUID [FK]",
        "agent_name: VARCHAR(64)",
        "evaluation_score: FLOAT",
        "trace_id: VARCHAR(64) [UQ]"
    ]
    draw_card(ax, 36, 5, 28, 38, title="TABLE: agent_runs", subtitle="Specialist Evaluation Traces",
              details=t_runs, bg=C_WHITE, border=C_SLATE, lw=1.2, r=2,
              title_size=8.5, sub_size=6.8, det_size=7.0, align="left", title_color=C_NAVY_DARK)

    # decisions
    t_dec = [
        "id: UUID [PK]",
        "business_id: UUID [FK]",
        "scenario_id: UUID [FK]",
        "strategy_type: VARCHAR(64)",
        "expected_outcome: JSONB",
        "status: VARCHAR(32)"
    ]
    draw_card(ax, 69, 5, 28, 38, title="TABLE: decisions", subtitle="Committed Decisions & Audits",
              details=t_dec, bg=C_WHITE, border=C_SLATE, lw=1.2, r=2,
              title_size=8.5, sub_size=6.8, det_size=7.0, align="left", title_color=C_NAVY_DARK)

    # Connectors to Row 2
    # businesses -> scenarios
    draw_conn(ax, 42, 52, 17, 43, label="1 : N", color=C_SLATE, lw=1.2)
    # scenarios -> agent_runs
    draw_conn(ax, 31, 24, 36, 24, label="1 : N", color=C_SLATE, lw=1.2)
    # scenarios -> decisions
    draw_conn(ax, 64, 24, 69, 24, label="1 : N", color=C_SLATE, lw=1.2)

    save_and_sync(fig, "figure_database_er.png")


# ==============================================================================
# 7. FIGURE 4.6: DEPLOYMENT TOPOLOGY (figure_deployment_arch.png)
# ==============================================================================
def generate_figure_4_6():
    print("Generating Figure 4.6: Deployment Architecture Diagram...")
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 96.5, "DECISIONGPT PRODUCTION DEPLOYMENT & CONTAINER TOPOLOGY",
            ha="center", fontsize=11.5, fontweight="bold", color=C_NAVY_DARK)
    ax.text(50, 93.2, "Multi-Container Docker Compose Stack with TLS Termination and Volume Isolation",
            ha="center", fontsize=8.0, fontstyle="italic", color=C_MUTED)

    # Outer Client Devices Box (Left)
    draw_card(ax, 3, 40, 20, 48, bg=C_LIGHT_BG, border=C_SLATE, lw=1.4, r=2)
    ax.text(13, 83, "CLIENT ACCESS", ha="center", fontsize=8.5, fontweight="bold", color=C_NAVY_DARK)
    ax.text(13, 80, "(Corporate LAN / Internet)", ha="center", fontsize=7.0, fontstyle="italic", color=C_MUTED)
    client_lines = [
        "• Desktop Web Browsers\n  (Chrome, Edge, Safari)",
        "• Responsive Mobile Clients\n  (Tablets & Smartphones)",
        "• Microphone & Audio I/O\n  (Speech recognition/TTS)"
    ]
    for i, line in enumerate(client_lines):
        ax.text(4.5, 74 - i*11, line, ha="left", fontsize=7.0, color=C_SLATE)

    draw_conn(ax, 23, 64, 28, 64, "HTTPS:443", lw=1.4)

    # Server Boundary Box (Center/Right)
    box_server = FancyBboxPatch((27, 4), 70, 86, boxstyle="round,pad=0,rounding_size=2",
                                linewidth=1.6, edgecolor=C_BLUE_BORDER, facecolor="#f8fafc", linestyle="--")
    ax.add_patch(box_server)
    ax.text(62, 86.5, "DOCKER COMPOSE HOST INFRASTRUCTURE (Linux VPS / Developer Workstation)",
            ha="center", fontsize=8.5, fontweight="bold", color=C_BLUE_TEXT)

    # Container 1: Reverse Proxy (Nginx)
    c1_details = [
        "• Nginx 1.25 Alpine image",
        "• SSL/TLS 1.3 termination",
        "• Static assets caching & Gzip",
        "• CORS header injection",
        "• Rate-limiting protection"
    ]
    draw_card(ax, 29, 44, 21, 38, title="REVERSE PROXY", subtitle="Nginx Container (Port 80/443)",
              details=c1_details, bg=C_WHITE, border=C_CYAN_BORDER, lw=1.2, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.5, align="left", title_color=C_CYAN_TEXT)

    # Proxy routes
    draw_conn(ax, 50, 68, 55, 68, "Proxy Pass :3000", lw=1.2)
    draw_conn(ax, 50, 52, 55, 34, "Proxy Pass :8000", lw=1.2)

    # Container 2: Frontend (Next.js)
    c2_details = [
        "• Node.js 20+ Alpine image",
        "• Next.js 14 production build",
        "• Server-side rendering (SSR)",
        "• Internal API proxying",
        "• Port: 3000 (Internal bridge)"
    ]
    draw_card(ax, 55, 52, 38, 30, title="FRONTEND CONTAINER", subtitle="Next.js 14 Web Application",
              details=c2_details, bg=C_WHITE, border=C_BLUE_BORDER, lw=1.2, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.5, align="left", title_color=C_BLUE_TEXT)

    # Container 3: Backend (FastAPI)
    c3_details = [
        "• Python 3.11 Slim image · 4 Uvicorn ASGI workers",
        "• FastAPI REST routing & Pydantic v2 schemas",
        "• scikit-learn / XGBoost model inference",
        "• Multi-agent dialectical debate engine",
        "• Port: 8000 (Internal bridge)"
    ]
    draw_card(ax, 55, 18, 38, 30, title="BACKEND CONTAINER", subtitle="FastAPI ASGI Application Core",
              details=c3_details, bg=C_WHITE, border=C_PURPLE_BORDER, lw=1.2, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.5, align="left", title_color=C_PURPLE_TEXT)

    # Container 4 & Volume: Database & Storage (Bottom left of server box)
    c4_details = [
        "• PostgreSQL 16 / SQLite",
        "• Persistent Docker volume mount",
        "• Snappy-compressed Parquet store",
        "• Port: 5432 (Isolated network)"
    ]
    draw_card(ax, 29, 6, 21, 34, title="DATA TIER", subtitle="PostgreSQL & Parquet Volume",
              details=c4_details, bg=C_WHITE, border=C_AMBER_BORDER, lw=1.2, r=2,
              title_size=8.0, sub_size=6.8, det_size=6.5, align="left", title_color=C_AMBER_TEXT)

    # Backend to DB connection
    draw_conn(ax, 55, 24, 50, 24, "SQLAlchemy 2.0 Pool", lw=1.2)

    save_and_sync(fig, "figure_deployment_arch.png")


if __name__ == "__main__":
    print("=" * 70)
    print("GENERATING CLEAN, PUBLICATION-GRADE DIAGRAMS FOR DECISIONGPT REPORT")
    print("=" * 70)
    generate_figure_3_1()
    generate_figure_4_1()
    generate_figure_4_2()
    generate_figure_4_3()
    generate_figure_4_4()
    generate_figure_4_5()
    generate_figure_4_6()
    print("=" * 70)
    print("ALL 7 DIAGRAMS SUCCESSFULLY CREATED & SYNCHRONIZED!")
    print("=" * 70)
