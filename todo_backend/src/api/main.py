from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.api.db import (
    list_todos as db_list_todos,
    create_todo as db_create_todo,
    update_todo as db_update_todo,
    toggle_todo as db_toggle_todo,
    delete_todo as db_delete_todo,
)

app = FastAPI(
    title="Todo Backend API",
    description="REST API for managing Todo tasks (create, read, update, toggle, delete).",
    version="1.0.0",
    openapi_tags=[
        {"name": "Health", "description": "Service health and diagnostics"},
        {"name": "Todos", "description": "Operations for managing todo tasks"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TodoBase(BaseModel):
    title: str = Field(..., description="Short title of the task", min_length=1)
    description: Optional[str] = Field(None, description="Optional detailed description")


class TodoCreate(TodoBase):
    pass


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated title")
    description: Optional[str] = Field(None, description="Updated description")
    completed: Optional[bool] = Field(None, description="Updated completion flag")


class TodoOut(BaseModel):
    id: int = Field(..., description="Unique identifier")
    title: str = Field(..., description="Title of the task")
    description: Optional[str] = Field(None, description="Detailed description")
    completed: bool = Field(..., description="Completion status")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


@app.get("/", tags=["Health"], summary="Health Check")
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/todos",
    response_model=List[TodoOut],
    tags=["Todos"],
    summary="List Todos",
    description="Retrieve all todos ordered by creation time descending.",
    responses={200: {"description": "A list of todos."}},
)
def get_todos():
    """Return all todos."""
    rows = db_list_todos()
    # Ensure 'completed' is boolean
    for r in rows:
        r["completed"] = bool(r["completed"])
    return rows


# PUBLIC_INTERFACE
@app.post(
    "/todos",
    response_model=TodoOut,
    tags=["Todos"],
    summary="Create Todo",
    description="Create a new todo item.",
    responses={
        201: {"description": "Todo created."},
        400: {"description": "Validation error."},
    },
    status_code=201,
)
def create_todo(payload: TodoCreate):
    """Create a new todo and return it."""
    created = db_create_todo(payload.title, payload.description)
    created["completed"] = bool(created["completed"])
    return created


# PUBLIC_INTERFACE
@app.put(
    "/todos/{id}",
    response_model=TodoOut,
    tags=["Todos"],
    summary="Update Todo",
    description="Update fields (title, description, completed) of a todo.",
    responses={
        200: {"description": "Updated todo."},
        404: {"description": "Todo not found."},
    },
)
def put_todo(
    id: int = Path(..., description="ID of the todo to update", ge=1),
    payload: TodoUpdate = ...,
):
    """Update a todo and return the updated row."""
    updated = db_update_todo(
        todo_id=id,
        title=payload.title if payload.title is not None else None,
        description=payload.description if payload.description is not None else None,
        completed=payload.completed if payload.completed is not None else None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Todo not found")
    updated["completed"] = bool(updated["completed"])
    return updated


# PUBLIC_INTERFACE
@app.patch(
    "/todos/{id}/toggle",
    response_model=TodoOut,
    tags=["Todos"],
    summary="Toggle Todo",
    description="Flip the completion status of a todo.",
    responses={
        200: {"description": "Toggled todo."},
        404: {"description": "Todo not found."},
    },
)
def patch_toggle_todo(id: int = Path(..., description="ID of the todo to toggle", ge=1)):
    """Toggle the 'completed' status of the specified todo."""
    updated = db_toggle_todo(todo_id=id)
    if not updated:
        raise HTTPException(status_code=404, detail="Todo not found")
    updated["completed"] = bool(updated["completed"])
    return updated


# PUBLIC_INTERFACE
@app.delete(
    "/todos/{id}",
    tags=["Todos"],
    summary="Delete Todo",
    description="Delete a todo by its identifier.",
    responses={
        204: {"description": "Todo deleted."},
        404: {"description": "Todo not found."},
    },
    status_code=204,
)
def delete_todo(id: int = Path(..., description="ID of the todo to delete", ge=1)):
    """Delete a todo. Returns 204 on success or 404 if not found."""
    success = db_delete_todo(todo_id=id)
    if not success:
        raise HTTPException(status_code=404, detail="Todo not found")
    return None
