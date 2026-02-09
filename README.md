 JewelryOps AI Agent (AutoGen + MCP)

A tool-using AI agent for JewelryOps (inventory and customer management for jewelry retailers) built with AutoGen and MCP servers.  
The agent behaves like a real agent – it runs in a loop (observe → decide → act → observe), chooses tools dynamically, maintains context across steps, asks clarifying questions, and checks for confirmation before side-effecting actions.

# Stack

- AutoGen – conversational agent framework with function calling and streaming
- FastAPI – backend API and WebSocket server
- 3 local MCP servers – Customers (CRM), Orders & Inventory, Communications (internal notes)
- 3 custom tools – `extract_entities`, `summarize_state`, `check_requires_confirmation`
- Streamlit – chat UI consuming WebSocket token stream
- SQLite – simple persistence
- Config – `pydantic-settings` with `.env`

# How to run

 1. Install and run locally

```bash
# From repo root
cd test_task2
uv sync         # or: pip install -e .
cp env.example .env
# Set OPENAI_API_KEY in .env or export it
uv run uvicorn jewelryops.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Health check: `GET /health`
- WebSocket chat: `ws://localhost:8000/ws/chat`

 2. Streamlit UI (WebSocket streaming)

With the FastAPI app running:

```bash
uv run streamlit run client/app.py
```

The Streamlit app connects to `ws://localhost:8000/ws/chat` and renders the assistant response token-by-token using WebSockets.

# Tools and MCPs

 Combined JewelryOps MCP (SQLite-backed)

`mcp_servers/jewelryops_mysql/server.py` exposes a single MCP server backed by a SQLite database, combining:

- Customers (CRM) – `get_customer`, `list_customers`, `search_customers`
- Orders & Inventory – `get_order`, `list_orders`, `get_inventory_item`, `list_inventory`, `check_stock`
- Communications / Notes – `get_notes`, `add_note`

On first run, the server creates tables and inserts mock data (customers like Lisa Park, orders, SKUs, and internal notes).

 Mock Notion MCP (issues tracker)

`mcp_servers/notion_mock/server.py` simulates a Notion database of issues:

- `get_issue`, `list_issues`, `create_issue`
- Stores data in `mcp_servers/notion_mock/data/issues.json`

 Mock Gmail MCP (emails)

`mcp_servers/gmail_mock/server.py` simulates a Gmail integration:

- `list_emails`, `search_emails`, `send_email`
- Stores data in `mcp_servers/gmail_mock/data/emails.json`


 Custom tools (3)

- `extract_entities` – Pull order IDs, customer IDs, and SKUs from natural language so the agent can call MCP tools with precise identifiers.
- `summarize_state` – Compact the recent investigation history and notes into a shorter summary the agent can rely on later instead of rereading the whole transcript.
- `check_requires_confirmation` – Decide whether a proposed action (refunds, cancellations, inventory updates, adding notes) should be confirmed by the user before execution.

# Context and tool selection

- Context management: Per `session_id` conversation state is kept in memory (`messages`, `investigation_summary`, `tool_calls_count`) via a lightweight `SessionState`. The AutoGen agent's system message includes recent conversation history and investigation summaries so it can maintain context across turns.
- Tool selection: The AutoGen agent uses OpenAI function calling to decide which MCP tools or custom tools to call based on the conversation; there is no hard-coded workflow for specific scenarios.
- Side effects: Before calling tools with side effects (like `add_note`), the agent is instructed to call `check_requires_confirmation` and ask the user for approval when needed.
