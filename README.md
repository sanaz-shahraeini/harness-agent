# Python Agent & Agentic Harness

An experimental and evolutionary Python project showcasing the development of autonomous AI agents from simple single-turn completion prompts up to a full multi-tool, Model Context Protocol (MCP)-enabled agentic harness with persistent memory.

---

## 🌟 Overview

This repository demonstrates step-by-step how to construct autonomous AI agents using Python, OpenRouter, OpenAI-compatible APIs, and local LLMs (such as Ollama):

- **Evolutionary Steps (`v0.py` – `v4.py`)**: Progressive iterations introducing conversation loops, structured tool calling, local filesystem interactions, and memory persistence.
- **Unified Agent Harness (`harness.py`)**: An advanced async harness that integrates Model Context Protocol (MCP) servers (e.g., fetch, time), workspace filesystem operations, persistent Markdown memory (`memory.md`), and seamless model switching (OpenRouter, local Ollama, OpenAI GPT).

---

## 🚀 Evolution Roadmap

| Script | Stage | Description |
|---|---|---|
| **`v0.py`** | Basic Chatbot | Simple interactive terminal chat with LLM via OpenRouter API. |
| **`v1.py`** | Multi-Turn Conversation | Preserves chat history and context across turns in memory. |
| **`v2.py`** | Function / Tool Calling | Integrates native function calling (calculator, search/mock tools). |
| **`v3.py`** | Filesystem Sandbox | Adds sandboxed file tools (`read_file`, `write_file`, `list_files`) within `./workspace/`. |
| **`v4.py`** | Persistent Memory | Introduces long-term memory via `memory.md` so the agent remembers user preferences across sessions. |
| **`harness.py`** | Full Agentic Harness | Async runtime with dynamic MCP tool discovery, workspace sandboxing, persistent memory, and multi-model switching. |

---

## 🛠 Features

- **Model Agnostic**: Switch easily between OpenRouter (free/paid cloud models), local Ollama instances (`qwen2.5`), or OpenAI GPT.
- **Model Context Protocol (MCP)**: Native support for MCP servers defined in `mcp_servers.json` (such as `mcp-server-fetch` and `mcp-server-time`).
- **Sandboxed Workspace**: Safe file inspection and generation restricted to the `workspace/` directory.
- **Long-term Memory**: Reads and updates key user facts or guidelines in `memory.md`.
- **Modern Packaging**: Configured with `uv` and `pyproject.toml` for fast dependency resolution.

---

## 📂 Project Structure

```text
├── harness.py                # Full-featured agent harness (MCP + memory + tools)
├── v0.py - v4.py             # Evolutionary agent prototypes (v0 to v4)
├── mcp_servers.json          # Configuration for MCP servers
├── memory.md                 # Agent's persistent long-term memory
├── workspace/                # Sandboxed directory for agent file read/write
├── pyproject.toml            # Project dependencies and packaging settings
├── uv.lock                   # Lockfile for reproducible environment
├── .env.example              # Sample environment variables template
└── agentic_harness_guide.html# Visual/interactive guide explaining the agent architecture
```

---

## ⚡ Getting Started

### 1. Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/sanaz-shahraeini/harness-agent.git
cd harness-agent

# Using uv (recommended)
uv sync

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 3. Environment Setup

Create a `.env` file in the root directory:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
# Optional:
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. Running the Agent

Run individual versions:
```bash
python v0.py
# or
python v4.py
```

Run the full harness:
```bash
python harness.py
```

---

## ⚙️ MCP Server Configuration (`mcp_servers.json`)

You can attach external tools using MCP servers:

```json
{
  "mcpServers": {
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

---

## 📜 License

MIT License. Feel free to use and adapt for your own agentic experiments!
