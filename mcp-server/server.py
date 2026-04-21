"""
Minimal MCP server exposed over SSE transport.

Runs as an independent container. Any MCP-compatible client can connect to:
    http://<host>:8000/sse

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

mcp = FastMCP(
    name="tasks-mcp",
    instructions=(
        "An in-memory task tracker. Use the available tools to list, add and "
        "complete tasks. All state lives inside this container only."
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
    print(f"[tasks-mcp] SSE listening on http://{host}:{port}/sse", flush=True)
    mcp.run(transport="sse")
