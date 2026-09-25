# Dola Render Gateway

A high-performance session coordinator and OpenAI-compatible video generation API service.

Provides automated browser session isolation, task queue distribution, extended duration handling, and an intuitive web management dashboard.

---

## 🌟 Key Capabilities

1. **OpenAI-Compatible Video API**:
   - `POST /v1/videos/generations`: Submit generation tasks with prompt, aspect ratio, duration (`10s`, `15s`, `30s`), and reference images.
   - `GET /v1/videos/<id>`: Poll task lifecycle (`queued` -> `processing` -> `completed` / `failed`).
   - High-speed MP4 streaming and static asset delivery.
2. **Extended Duration & High-Definition Media Export**:
   - Integrated browser automation profile for managing extended duration options.
   - Direct original quality stream extraction and processing.
3. **Multi-Account Browser Pool**:
   - Manages multiple persistent browser profiles in `accounts/`.
   - Automatic concurrency management, mutual exclusion, and session rotation.
   - Built-in verification handling.
4. **Admin Web Dashboard**:
   - Real-time dashboard at `/web` to monitor generation trends, success rate, account statuses, task queues, and API key management.
5. **Model Context Protocol (MCP) Integration**:
   - Streamable HTTP JSON-RPC 2.0 server at `/mcp` supporting Claude Desktop, Cursor, ChatGPT, VS Code (Cline/Roo Code), and Codex CLI.
   - 5 standardized MCP tools: `dola_create_video`, `dola_get_task_status`, `dola_list_tasks`, `dola_list_accounts`, `dola_download_video`.
   - Built-in CSPRNG 256-bit API key generator (`dolamcp_...`) with one-time secret display.
   - Comprehensive MCP usage dashboard & quota tracking (requests, downloads, successes, failures, daily limits, per-key stats).

---

## 📁 Repository Structure

```
dola-render-gateway/
├── server.py              # FastAPI server (OpenAI-compatible video API, MCP routes & admin)
├── mcp_integration.py     # MCP JSON-RPC 2.0 gateway, tools dispatcher, quota & usage engine
├── browser_pool.py        # Account pool concurrency manager and task scheduler
├── browser.py             # Playwright persistent context launcher
├── video_worker_ui.py     # UI automation worker with verification handler
├── video_worker.py        # Protocol worker and status polling
├── store.py               # SQLite task persistence and API key storage
├── dola_client.py         # API client communication module
├── media.py               # Reference media processor
├── config.py              # Configuration & environment variables
├── add_account.py         # Automated account profile setup
├── config/
│   └── mcp-integration.manifest.yaml  # Standardized MCP manifest and tool schemas
├── web/
│   └── index.html         # Single-page admin management dashboard with MCP tab
└── extensions/
    └── dola30/            # Chromium extension profile
```

---

## 🚀 Quick Start

### 1. Requirements
* Python 3.11+
* Chrome / Chromium browser
* Proxy with JP/KR egress

### 2. Setup Environment
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure
```bash
# Set your proxy configuration
export DOLA_PROXY="http://127.0.0.1:7890"

# Set API key for client authentication (required in production)
export DOLA_API_KEYS="sk-your-secret-key"

# Admin dashboard password (required in production)
export DOLA_ADMIN_KEY="change-me"

# Concurrency limits
export DOLA_MAX_CONCURRENCY=3
```

Authentication fails closed: the server refuses to start unless `DOLA_ADMIN_KEY`
and at least one client API key are configured. For local-only development you
can opt out explicitly with `DOLA_HOST=127.0.0.1` and
`DOLA_ALLOW_UNAUTHENTICATED=1`; the flag alone is not enough, because the real
uvicorn bind address can differ from `DOLA_HOST`.

Stored videos are no longer served by an unauthenticated static mount.
`/videos/<file>` requires the owning API key (`Authorization: Bearer ...`), a
valid admin key, or a signed token generated for dashboard playback.

### 4. Start Server
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```
Open **http://127.0.0.1:8000/web** to access the Admin Dashboard.

`GET /health` returns aggregate counters for anonymous callers; the per-account
list is only included for an authenticated admin (or in loopback dev mode).

### 5. Connecting with AI Assistants via MCP

1. Open **http://127.0.0.1:8000/web** and navigate to the **MCP Integration** tab.
2. Generate an API Key (CSPRNG 256-bit with prefix `dolamcp_`).
3. Add the MCP endpoint to your client configuration:

**Cursor (`.cursor/mcp.json`):**
```json
{
  "mcpServers": {
    "dola-render": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "x-api-key": "dolamcp_YOUR_KEY_HERE"
      }
    }
  }
}
```

**Claude Desktop (`claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "dola-render": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sse",
        "http://127.0.0.1:8000/mcp"
      ],
      "env": {
        "DOLA_API_KEY": "dolamcp_YOUR_KEY_HERE"
      }
    }
  }
}
```

**VS Code (Roo Code / Cline):**
```json
{
  "mcpServers": {
    "dola-render": {
      "transport": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "x-api-key": "dolamcp_YOUR_KEY_HERE"
      }
    }
  }
}
```


### 🌐 SonicVoice (For Voice Clone)

[![Website](https://img.shields.io/badge/Website-SonicVoice.pro-6366f1?style=for-the-badge&logo=google-chrome&logoColor=white)](https://sonicvoice.pro)

### 💬 Admin & Support

[![Zalo](https://img.shields.io/badge/Zalo-Nhóm%20Zalo-0068FF?style=for-the-badge&logoColor=white)](https://zalo.me/g/jvwa05y9id3apkgfocw0)

---

## 📜 License
For educational and internal testing purposes.
