# Code Quality & Technical Debt Detector

A multi-agent system that automatically analyzes a codebase to detect **security
vulnerabilities, technical debt, and maintainability issues**, prioritizes findings
by severity (**P0–P3**), and turns them into concrete actions (GitHub PR comments,
Jira tickets).

Built as a four-week internship project, where each stage builds on the previous one:
from source parsing, to static analysis, to multi-agent orchestration, to external
integrations.

---

## Architecture

The system is organized into layers, each with a single responsibility:

| Layer | Responsibility | Main files |
|---|---|---|
| **Ingestion** | Parse source into an AST, split into functions, extract metadata | `ingest.py` |
| **Vector DB** | Embed functions and run semantic similarity search | `embed_store.py` |
| **Static Analysis** | Rule-based + tool-based detection, P0–P3 severity | `analyzer.py`, `tools.py` |
| **Orchestration** | Supervisor-driven flow, cross-file search, human approval | `graph_app.py`, `pipeline.py` |
| **Action & Reporting** | MCP actions (GitHub/Jira), report, dashboard | `mcp_server.py`, `mcp_client.py`, `report_html.py`, `streamlit_app.py` |

**Data flow:** source file → AST parsing → function-level chunking + metadata →
embedding + vector DB → static analysis (custom detectors + bandit/semgrep) →
dedup + prioritization → LangGraph orchestration (cross-file search + human-in-the-loop)
→ MCP actions + report + dashboard.

---

## Key Features

- **Multi-language parsing** with tree-sitter (C, Python, JavaScript, Java) and an
  AST-based approach that reasons about structure rather than text.
- **Semantic similarity search** over a Qdrant vector database to find where the same
  vulnerability pattern recurs across different files (cross-file detection).
- **Unified finding schema** that merges custom rule-based detectors with established
  tools (`semgrep`, `bandit`), with **graceful degradation** when a tool is unavailable.
- **Multi-agent orchestration** with LangGraph, including a **human-in-the-loop** approval
  step (interrupt + checkpointer) before any action is taken on critical findings.
- **External integration via MCP** (Model Context Protocol): a FastMCP server exposes
  `create_pr_comment` and `create_ticket` tools; the client discovers and calls them.
- **Trend-aware reporting** (HTML/Markdown) and an interactive **Streamlit dashboard**
  with a file × severity heat map.

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

> **Note (Windows):** if `pip install mcp` reports a PyJWT conflict, run
> `pip install mcp --ignore-installed PyJWT`.

---

## Usage

Each layer can be run independently against the sample `repo/` folder:

```bash
# Single-file ingestion (AST + metadata output)
python ingest.py repo/db.c c

# Semantic similarity search across the repo
python embed_store.py

# Single-file static analysis (P0–P3 findings)
python pipeline.py repo/db.c c

# Multi-agent orchestration (full repo scan + human-in-the-loop approval)
python graph_app.py repo

# MCP actions (PR comments + Jira tickets -> written to mcp_output/)
python mcp_client.py repo

# Trend-aware technical debt report (HTML + Markdown -> reports/)
python report_html.py repo

# Interactive dashboard (file-based heat map)
streamlit run streamlit_app.py
```

---

## Design Notes

- **The LLM is optional, not required.** The explanation/refactor layer (`explain.py`)
  only activates when `ANTHROPIC_API_KEY` is set; without it, the system remains fully
  functional. The LLM is an *enrichment* layer, not a dependency — detection is done by
  deterministic, rule-based components.
- **Swappable embedding.** A lightweight token-based embedding is used by default so the
  pipeline runs offline. Switching to a real neural model (e.g. `nomic-embed-code`)
  requires changing a single function in `embed_store.py`.
- **Swappable MCP target.** The MCP server writes results to local JSON for the demo.
  Switching to a real GitHub/Jira MCP server is only a client-side address change — the
  pipeline is unchanged.
- **semgrep is optional.** If `semgrep` is not installed, its adapter returns an empty
  list and the pipeline continues with the custom detectors and `bandit`.

---

## Tech Stack

Python · tree-sitter · Qdrant · LangGraph · MCP (Model Context Protocol) ·
semgrep · bandit · Streamlit · Plotly
