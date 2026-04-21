"""
Minimal MCP server exposed over Streamable HTTP transport.

Runs as an independent container. Any MCP-compatible client can connect to:
    http://<host>:8000/mcp

Tools exposed:
    - list_tasks(status?)        list tasks (optionally filtered)
    - add_task(title, priority)  add a task and return it
    - complete_task(id)          mark a task as completed
    - stats()                    summary counters

State is in-memory for demo purposes.
"""
from __future__ import annotations

import itertools
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

Priority = Literal["low", "medium", "high"]
Status = Literal["open", "done"]


@dataclass
class Task:
    id: int
    title: str
    priority: Priority
    status: Status = "open"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_id_counter = itertools.count(1)
_tasks: dict[int, Task] = {}


def _seed() -> None:
    for title, pri in [
        ("Review Agent Framework samples", "high"),
        ("Write blog post about MCP", "medium"),
        ("Open PR to microsoft/agent-framework", "high"),
    ]:
        tid = next(_id_counter)
        _tasks[tid] = Task(id=tid, title=title, priority=pri)  # type: ignore[arg-type]


_seed()

# DNS-rebinding protection blocks non-localhost Host headers by default.
# Inside Docker Compose the client reaches us via the service name ("mcp-server"),
# so we add the expected hosts to the allow-list. Extra names can be passed in
# MCP_ALLOWED_HOSTS (comma-separated) — useful behind a reverse proxy.
_default_hosts = ["mcp-server", "mcp-server:8000", "localhost", "localhost:8000", "127.0.0.1", "127.0.0.1:8000"]
_extra_hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]

mcp = FastMCP(
    name="tasks-mcp",
    instructions=(
        "An in-memory task tracker. Use the available tools to list, add and "
        "complete tasks. All state lives inside this container only."
    ),
    transport_security=TransportSecuritySettings(
        allowed_hosts=_default_hosts + _extra_hosts,
    ),
)


@mcp.tool()
def list_tasks(status: Status | None = None) -> list[dict]:
    """List tasks. Optionally filter by status ('open' | 'done')."""
    items = _tasks.values()
    if status is not None:
        items = (t for t in items if t.status == status)
    return [asdict(t) for t in items]


@mcp.tool()
def add_task(title: str, priority: Priority = "medium") -> dict:
    """Add a task and return the created record."""
    if not title or not title.strip():
        raise ValueError("title must be non-empty")
    tid = next(_id_counter)
    task = Task(id=tid, title=title.strip(), priority=priority)
    _tasks[tid] = task
    return asdict(task)


@mcp.tool()
def complete_task(id: int) -> dict:
    """Mark a task as completed. Returns the updated task."""
    task = _tasks.get(id)
    if task is None:
        raise ValueError(f"task {id} not found")
    task.status = "done"
    return asdict(task)


@mcp.tool()
def stats() -> dict:
    """Return summary counters for the current task list."""
    total = len(_tasks)
    done = sum(1 for t in _tasks.values() if t.status == "done")
    return {
        "total": total,
        "done": done,
        "open": total - done,
        "by_priority": {
            p: sum(1 for t in _tasks.values() if t.priority == p)
            for p in ("low", "medium", "high")
        },
    }


if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.settings.host = host
    mcp.settings.port = port
    print(f"[tasks-mcp] Streamable HTTP listening on http://{host}:{port}/mcp", flush=True)
    mcp.run(transport="streamable-http")
