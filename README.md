# MCP Docker Starter — Agent Framework + MCP over Docker

[![.NET](https://img.shields.io/badge/.NET-8.0-512BD4?logo=dotnet&logoColor=white)](https://dotnet.microsoft.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-v2-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-black)](https://modelcontextprotocol.io/)
[![Agent Framework](https://img.shields.io/badge/Microsoft_Agent_Framework-preview-0078D4?logo=microsoft&logoColor=white)](https://github.com/microsoft/agent-framework)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

**Two containers. One agent conversation.**

A **Python MCP server** and a **Microsoft Agent Framework (.NET) client** wired together with **Docker Compose** — showing how to compose agents with remote tools over real service-to-service networking.

```
┌──────────────────────┐  Streamable HTTP /mcp         ┌──────────────────────┐
│  agent-client (.NET) │  ─────────────────────▶  │  mcp-server (Python) │
│  Microsoft.Agents.AI │        JSON-RPC          │      FastMCP          │
│  + Azure OpenAI      │                          │  list/add/complete    │
└──────────────────────┘                          └──────────────────────┘
            │                                                 │
            └─────────── mcp-net (bridge network) ────────────┘
```

> Part of a Docker-first series for Microsoft Agent Framework:
> [`agent-framework-devcontainer`](https://github.com/ppiova/agent-framework-devcontainer) · [`mcp-docker-starter`](https://github.com/ppiova/mcp-docker-starter) · [`ai-agents-compose-stack`](https://github.com/ppiova/ai-agents-compose-stack)

---

## What's interesting here (for Docker-curious readers)

| Pattern shown                 | Where to look                                  |
| ----------------------------- | ---------------------------------------------- |
| Polyglot compose (Python + .NET) | `compose.yaml`                              |
| Service-to-service via bridge network | `networks: mcp-net`                    |
| Service discovery by name     | Client connects to `http://mcp-server:8000/mcp` |
| Non-root containers           | Both `Dockerfile`s use dedicated system users  |
| Healthcheck on the MCP server | `mcp-server/Dockerfile`                         |
| Multi-stage .NET build, Alpine runtime | `agent-client/Dockerfile`             |
| Client readiness wait         | `WaitForEndpointAsync` in `Program.cs`          |
| Secrets via `.env`, never committed | `.gitignore` + `.dockerignore`            |

---

## Requirements

- Docker Desktop (or Docker Engine + Compose v2)
- An **Azure OpenAI** resource with a chat deployment (e.g. `gpt-4o-mini`)

---

## Quickstart

```bash
git clone https://github.com/ppiova/mcp-docker-starter.git
cd mcp-docker-starter
cp .env.example .env
# edit .env with your Azure OpenAI values
docker compose up --build
```

You should see (abbreviated):

```
mcp-tasks-server  | [tasks-mcp] SSE listening on http://0.0.0.0:8000/mcp
mcp-agent-client  | ✅ MCP host reachable at http://mcp-server:8000/
mcp-agent-client  | 🔌 Connecting to MCP: http://mcp-server:8000/mcp
mcp-agent-client  | 🧰 MCP tools discovered: list_tasks, add_task, complete_task, stats
mcp-agent-client  | > Prompt: Mostrame el estado actual de tareas...
mcp-agent-client  | --- Respuesta (streaming) ---
mcp-agent-client  | Tareas abiertas:
mcp-agent-client  | 1. Review Agent Framework samples (high)
mcp-agent-client  | 2. Write blog post about MCP (medium)
mcp-agent-client  | ...
```

### Ask your own question

```bash
docker compose run --rm agent-client "Completá la tarea 1 y mostrame las stats"
```

---

## The MCP server

`mcp-server/server.py` uses **FastMCP** (Python) to expose 4 tools:

| Tool             | Args                                 | Returns                        |
| ---------------- | ------------------------------------ | ------------------------------ |
| `list_tasks`     | `status? = 'open' \| 'done'`         | array of tasks                 |
| `add_task`       | `title: str, priority: 'low'\|'medium'\|'high'` | new task       |
| `complete_task`  | `id: int`                            | updated task                   |
| `stats`          | —                                    | counters + priority breakdown  |

State is **in-memory** on purpose — it's a starter. Swap for Redis/SQL when you need persistence (add a `redis` service to `compose.yaml`).

### Debug the MCP server directly

It's exposed on `localhost:8000` for convenience. Use the official **[MCP Inspector](https://github.com/modelcontextprotocol/inspector)**:

```bash
npx @modelcontextprotocol/inspector
# Then connect to http://localhost:8000/mcp  (transport: streamable-http)
```

> **Note on DNS-rebinding protection** — the Python MCP SDK rejects unknown Host headers by default. Inside Docker Compose the client reaches the server via the service name (`mcp-server:8000`), so we explicitly allow it via `TransportSecuritySettings(allowed_hosts=...)`. If you deploy behind a reverse proxy / ingress, add the extra hostnames through the `MCP_ALLOWED_HOSTS` env var (comma-separated).

---

## The Agent Framework client

`agent-client/Program.cs` (C#, .NET 8) does four things:

1. Waits for the MCP host to be reachable (compose `depends_on` + app-level readiness check).
2. Opens an **SSE** MCP connection via `ModelContextProtocol` client SDK.
3. Lists tools from the MCP server and casts them into `AITool`s.
4. Creates an `AIAgent` via **`Microsoft.Agents.AI`** bound to Azure OpenAI, with the MCP tools attached.

The model decides which MCP tools to call based on the prompt. No mock, no handwritten wrappers — MCP tools flow straight into the Agent Framework.

---

## Extending this starter

- **Add persistence** — swap the in-memory dict for Redis/SQLite and add a `redis` / `db` service.
- **Add more MCP tools** — decorate with `@mcp.tool()`, they're auto-discovered by the client.
- **Scale the client** — run N agent-client replicas against a single MCP server.
- **Production hardening** — put the MCP server behind a reverse proxy, enable auth, ship traces via OpenTelemetry (see [`ai-agents-compose-stack`](https://github.com/ppiova/ai-agents-compose-stack)).
- **Swap models** — point the client at OpenAI.com or Ollama using `Microsoft.Extensions.AI` providers.

---

## Project layout

```
.
├── .devcontainer/
│   └── devcontainer.json
├── agent-client/
│   ├── Dockerfile         # multi-stage, Alpine runtime, non-root
│   ├── AgentClient.csproj # .NET 8 + Microsoft.Agents.AI + ModelContextProtocol
│   └── Program.cs         # Connects to MCP, creates agent, streams response
├── mcp-server/
│   ├── Dockerfile         # Python 3.12-slim, non-root, healthcheck
│   ├── requirements.txt
│   └── server.py          # FastMCP + 4 tools + SSE transport
├── compose.yaml           # Two services on a private bridge network
├── .dockerignore
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

---

## Auth modes

Same pattern as the other repos in this series:

1. `AZURE_OPENAI_API_KEY` if set → key auth (simplest inside Docker).
2. Otherwise → `AzureCliCredential` (works in the Dev Container after `az login`).
3. Otherwise → `DefaultAzureCredential` (Managed Identity / env vars in production).

---

## License

[MIT](./LICENSE) — by [Pablo Piovano](https://github.com/ppiova) · Microsoft MVP in AI.
