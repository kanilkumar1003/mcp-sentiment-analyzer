# 🚀 Autonomous Market Sentiment & Competitor Intel Agent

> An MCP-powered agentic system that autonomously researches trending tech topics, analyzes market sentiment from multiple sources, generates professional reports, and creates interactive dashboards — all without human intervention.

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![MCP](https://img.shields.io/badge/Protocol-MCP-purple)](https://modelcontextprotocol.io)
[![Gemini](https://img.shields.io/badge/LLM-Gemini-orange?logo=google&logoColor=white)](https://ai.google.dev)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-green)](https://ollama.com)

---

## 📺 Demo Video

<!-- 🎬 PASTE YOUR YOUTUBE LINK BELOW -->
[![Watch the Demo](https://img.shields.io/badge/▶_Watch_Demo-YouTube-red?style=for-the-badge&logo=youtube)](YOUR_YOUTUBE_LINK_HERE)

> **🔗 YouTube:** [Link for demo video](https://youtu.be/K3zMVD7w9NA)

---

## 📌 Overview

This project implements a **fully autonomous agentic loop** using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). The agent:

1. **Fetches** real-time data from Hacker News and Reddit
2. **Analyzes** sentiment across the collected articles
3. **Persists** findings to a structured JSON log
4. **Generates** a professional Markdown report
5. **Creates** an interactive Prefab UI dashboard with charts, tables, and badges

All steps are orchestrated by an LLM (Gemini or Ollama) that decides which tool to call next — no hardcoded workflow.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   run_intel_agent.py                    │
│                  (Agentic Loop / Router)                │
│                                                         │
│   ┌──────────────┐          ┌──────────────┐            │
│   │  Gemini API  │    OR    │ Ollama Local │            │
│   │  (Online)    │          │  (Offline)   │            │
│   └──────┬───────┘          └──────┬───────┘            │
│          └──────────┬──────────────┘                    │
│                     ▼                                   │
│          FUNCTION_CALL / FINAL_ANSWER                   │
└─────────────────────┬───────────────────────────────────┘
                      │ MCP (stdio transport)
                      ▼
┌────────────────────────────────────────────────────────-─┐
│                 intel_mcp_server.py                      │
│                  (8 MCP Tools)                           │
│                                                          │
│  ┌────────────────-┐   ┌────────────────┐                │
│  │ fetch_hackernews│   │  fetch_reddit  │  ← Internet    │
│  └────────────────-┘   └────────────────┘                │
│  ┌────────────────-┐   ┌────────────────-┐               │
│  │ save_sentiment  │   │read_sentiment_  │  ← File CRUD  │
│  │                 │   │      log        │               │
│  └────────────────-┘   └────────────────-┘               │
│  ┌────────────────-┐   ┌────────────────-┐               │
│  │compare_topics   │   │generate_report  │  ← Analysis   │
│  └────────────────-┘   └────────────────-┘               │
│  ┌────────────────-┐   ┌────────────────-┐               │
│  │list_sandbox_    │   │  generate_ui    │  ← Output     │
│  │    files        │   │                 │               │
│  └────────────────-┘   └────────────────-┘               │
│                       │                                  │
│                       ▼                                  │
│                    sandbox/                              │
│              (all files confined here)                   │
└────────────────────────────────────────────────────────-─┘
```

---

## 🛠️ Tool Catalog (8 Tools)

| # | Tool | Category | Description |
|---|------|----------|-------------|
| 1 | `fetch_hackernews` | 🌐 Internet | Search Hacker News Algolia API (no auth required) |
| 2 | `fetch_reddit` | 🌐 Internet | Search Reddit public JSON API (no auth required) |
| 3 | `save_sentiment` | 💾 File CRUD | Append sentiment analysis to `intel_data.json` |
| 4 | `read_sentiment_log` | 📖 File CRUD | Read back all saved sentiment entries |
| 5 | `compare_topics` | 📊 Analysis | Side-by-side comparison of saved topics |
| 6 | `generate_report` | 📝 Analysis | Write a professional Markdown report |
| 7 | `list_sandbox_files` | 📂 Utility | List all files in the sandbox directory |
| 8 | `generate_ui` | 🎨 Prefab UI | Generate interactive dashboard (10+ widget types) |

### Supported UI Widgets
`stat` · `pie` · `bar` · `ring` · `sparkline` · `progress_list` · `table` · `text` · `badges`

---

## ⚡ Quick Start

### Prerequisites

- Python 3.10+
- A Gemini API key ([get one here](https://ai.google.dev/gemini-api/docs/api-key)) **OR** [Ollama](https://ollama.com) installed locally

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/mcp-sentiment-analyzer.git
cd mcp-sentiment-analyzer

# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

### Running the Agent

```bash
# Interactive mode (choose online/offline at startup)
python run_intel_agent.py

# Force Gemini (online)
python run_intel_agent.py --online

# Force Ollama (offline)
python run_intel_agent.py --offline
```

### For Ollama (Offline Mode)

```bash
# Install and start Ollama
ollama pull gemma3:4b
ollama serve

# Then run the agent
python run_intel_agent.py --offline
```

---

## 📂 Project Structure

```
assignment/
├── README.md                  ← You are here
├── requirements.txt           ← Python dependencies
├── .env.example               ← Template for API keys
├── .gitignore                 ← Git ignore rules
├── intel_mcp_server.py        ← MCP Tool Server (8 tools)
├── run_intel_agent.py         ← Agentic Loop (dual LLM mode)
└── sandbox/                   ← Sandboxed output directory
    ├── intel_data.json        ← Sentiment log (auto-generated)
    ├── deepseek_report.md     ← Markdown report (auto-generated)
    └── generated_app.py       ← Prefab UI dashboard (auto-generated)
```

---

## 🎯 Example Agent Run

```
╔══════════════════════════════════════════════════════════════╗
║  🚀  Autonomous Market Sentiment & Competitor Intel Agent   ║
║  Mode : ONLINE                                              ║
╚══════════════════════════════════════════════════════════════╝

✓ Connected to intel_mcp_server
✓ Loaded 8 tools

━━━ Iteration 1 ━━━
🤖 LLM: FUNCTION_CALL: fetch_hackernews|DeepSeek
  → fetch_hackernews(topic='DeepSeek')
  ← 1. DeepSeek v4 | 2091 pts | 1607 comments ...

━━━ Iteration 2 ━━━
🤖 LLM: FUNCTION_CALL: fetch_reddit|DeepSeek
  → fetch_reddit(topic='DeepSeek')
  ← 1. [r/technology] DeepSeek-V4 arrives ... | 3050 upvotes ...

━━━ Iteration 3 ━━━
🤖 LLM: FUNCTION_CALL: save_sentiment|DeepSeek|...|positive
  ← Saved sentiment for 'DeepSeek' (score=positive) → intel_data.json

━━━ Iteration 4 ━━━
🤖 LLM: FUNCTION_CALL: generate_report|DeepSeek|...
  ← Report saved → deepseek_report.md

━━━ Iteration 5 ━━━
🤖 LLM: FUNCTION_CALL: generate_ui|{"params": {"title": "DeepSeek Intel Dashboard", ...}}
  ← Successfully generated UI dashboard and saved to generated_app.py

━━━ Iteration 6 ━━━
🤖 LLM: FINAL_ANSWER: Successfully researched DeepSeek, analyzed sentiment, ...

══════════════════════════════════════
  ✅  Agent finished
══════════════════════════════════════

📁 Sandbox contents:
   deepseek_report.md  (614 bytes)
   generated_app.py    (2,284 bytes)
   intel_data.json     (359 bytes)
```

---

## 🔑 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Hacker News + Reddit** (no auth) | Free, reliable, and rich tech data without API key management |
| **JSON-lines** for storage | Simple append-only format, easy to parse, no DB overhead |
| **Dual LLM mode** | Flexibility — works with cloud API or fully offline |
| **Sandbox directory** | All file operations are confined to prevent accidental writes |
| **Retry logic** | Handles transient 503 errors and timeouts gracefully |
| **Widget key aliasing** | Handles LLM output variations (`title`↔`label`, `body`↔`content`) |
| **`compile()` check** | Validates generated Python code before writing to disk |

---

## 🧠 How It Works

1. **Agent Startup** → Connects to the MCP server via stdio, discovers all 8 tools
2. **System Prompt** → Instructs the LLM with the available tools and the FUNCTION_CALL/FINAL_ANSWER protocol
3. **Autonomous Loop** → The LLM decides which tool to call next based on prior results
4. **Tool Execution** → The MCP server executes the tool and returns the result
5. **Convergence** → After 5-6 iterations, the agent emits FINAL_ANSWER with all outputs saved to the sandbox

---

## 📜 License

This project is built for educational purposes as part of the EAG V3 (Agentic AI) course — Session 4: MCP.

---

## 🙏 Acknowledgments

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io) by Anthropic
- [Hacker News Algolia API](https://hn.algolia.com/api)
- [Reddit JSON API](https://www.reddit.com/dev/api/)
- [Prefab UI](https://github.com/prefab-cloud/prefab-ui) for dashboard generation
- [Google Gemini](https://ai.google.dev) and [Ollama](https://ollama.com) for LLM backends
