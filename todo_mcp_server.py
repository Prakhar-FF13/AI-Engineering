
import argparse
import uuid

from datetime import datetime, timezone
from threading import RLock
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field


# ============================================
# 1. MCP SERVER
# ============================================

mcp = FastMCP("Todo MCP Server")


# ============================================
# 2. PYDANTIC MODELS
# ============================================

class Todo(BaseModel):
    id: str
    title: str
    completed: bool = False
    created_at: datetime


class TodoList(BaseModel):
    todos: list[Todo]
    count: int


class DeleteTodoResponse(BaseModel):
    id: str
    deleted: bool
    message: str


# ============================================
# 3. IN-MEMORY STORAGE
# ============================================

todos: dict[str, Todo] = {}
todos_lock = RLock() # Reentrant lock


# ============================================
# 4. CREATE TODO
# ============================================

@mcp.tool
def create_todo(
    title: Annotated[
        str,
        Field(min_length=1, max_length=200)
    ],
) -> Todo:
    """Create a new TODO."""

    title = title.strip()

    if not title:
        raise ToolError("TODO title cannot be empty.")

    todo = Todo(
        id=uuid.uuid4().hex[:8],
        title=title,
        completed=False,
        created_at=datetime.now(timezone.utc),
    )

    with todos_lock:
        todos[todo.id] = todo

    return todo


# ============================================
# 5. LIST TODOS
# ============================================

@mcp.tool
def list_todos(
    completed: bool | None = None,
) -> TodoList:
    """List TODOs with an optional completion filter."""

    with todos_lock:
        result = [
            todo
            for todo in todos.values()
            if completed is None or todo.completed == completed
        ]

    return TodoList(
        todos=result,
        count=len(result),
    )


# ============================================
# 6. GET TODO
# ============================================

@mcp.tool
def get_todo(todo_id: str) -> Todo:
    """Get a TODO by ID."""

    with todos_lock:
        todo = todos.get(todo_id)

        if todo is None:
            raise ToolError(f"TODO {todo_id} not found.")

        return todo


# ============================================
# 7. COMPLETE TODO
# ============================================

@mcp.tool
def complete_todo(todo_id: str) -> Todo:
    """Mark a TODO as completed."""

    with todos_lock:
        todo = todos.get(todo_id)

        if todo is None:
            raise ToolError(f"TODO {todo_id} not found.")

        todo.completed = True

        return todo


# ============================================
# 8. DELETE TODO
# ============================================

@mcp.tool
def delete_todo(todo_id: str) -> DeleteTodoResponse:
    """Delete a TODO by ID."""

    with todos_lock:
        todo = todos.pop(todo_id, None)

        if todo is None:
            raise ToolError(f"TODO {todo_id} not found.")

    return DeleteTodoResponse(
        id=todo_id,
        deleted=True,
        message=f"TODO '{todo.title}' deleted successfully.",
    )


# ============================================
# 9. RESOURCE
# ============================================

@mcp.resource("todos://all")
def all_todos_resource() -> str:
    """Read all TODOs as JSON."""

    with todos_lock:
        result = TodoList(
            todos=list(todos.values()),
            count=len(todos),
        )

    return result.model_dump_json(indent=2)


# ============================================
# 10. SERVER ENTRY POINT
# ============================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")

    elif args.transport == "http":
        mcp.run(
            transport="http",
            host="127.0.0.1",
            port=8000,
        )
