# API Discovery Agent

An AI-powered agent that automates API integration discovery. Describe your use case in plain English, and the agent will discover APIs, test endpoints, validate feasibility, and generate a PDF report.

## What It Does

1. **Understand** - Asks clarifying questions about your integration needs
2. **Discover** - Searches 14,000+ APIs via APIs.guru or parses your OpenAPI spec
3. **Test** - Makes real HTTP calls to verify endpoints work
4. **Validate** - Maps your requirements to available endpoints and identifies gaps
5. **Report** - Generates a downloadable PDF report with verdict and recommendations

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
export ANTHROPIC_API_KEY=your-key-here

# 3. Run the app
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Demo

Click **"Load Petstore Demo"** in the sidebar, or type your own use case:

> "I want to build a pet adoption platform. I need to list available pets, get details of a specific pet, and place an order for adoption."

## Architecture

```
Streamlit UI (app.py) → Agent Loop (agent.py) → Claude Tool Use → Tools (tools.py)
```

- **app.py** - Chat UI with clickable button cards, tool expanders, PDF download
- **agent.py** - Claude tool_use agentic loop (~50 lines of core logic)
- **tools.py** - 8 tools: API directory search, spec parsing, auth, HTTP calls, validation, PDF
- **tool_definitions.py** - Tool schemas for Claude
- **config.py** - System prompt and configuration
- **pdf_report.py** - Professional PDF report generation

Built with the **Anthropic Python SDK** (no LangChain/CrewAI needed).

## Tools

| Tool | Purpose |
|------|---------|
| `lookup_api_directory` | Search APIs.guru (14K+ APIs) by name |
| `fetch_openapi_spec` | Parse OpenAPI/Swagger specs |
| `list_endpoints` | List all discovered endpoints |
| `search_endpoints` | Search endpoints by capability |
| `authenticate` | Bearer, API Key, Basic, OAuth2 |
| `call_api` | Make real HTTP requests |
| `validate_integration` | Evaluate feasibility with confidence score |
| `generate_pdf_report` | Create downloadable PDF report |

## Requirements

- Python 3.11+
- Anthropic API key
