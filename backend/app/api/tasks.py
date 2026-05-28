"""
Tasks API endpoints
Full CRUD for tasks with comments, assignments, and filtering
Implements kanban-style status transitions
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from math import ceil

from app.schemas import (
    TaskCreate, TaskUpdate, TaskResponse, CommentCreate, CommentResponse, PaginatedResponse
)
from app.security import get_current_user
from app.database import get_db

router = APIRouter()

# Valid status transitions (state machine)
VALID_TRANSITIONS = {
    "backlog": ["todo"],
    "todo": ["in_progress", "backlog"],
    "in_progress": ["in_review", "todo"],
    "in_review": ["done", "in_progress"],
    "done": ["in_progress"]
}


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Create a new task within a project.
    
    - Validates project membership
    - Optionally assigns to a team member
    - Sends notification if assigned (background task)
    """
    # Validate project exists and user is a member
    try:
        project = await db.projects.find_one({"_id": ObjectId(task_data.project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user["id"] not in project.get("team_members", []) and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You are not a member of this project")
    
    # Validate assignee if provided
    assignee_name = None
    if task_data.assignee_id:
        assignee = await db.users.find_one({"_id": ObjectId(task_data.assignee_id)})
        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")
        assignee_name = assignee["full_name"]
    
    now = datetime.now(timezone.utc)
    task_doc = {
        "title": task_data.title,
        "description": task_data.description,
        "project_id": task_data.project_id,
        "project_name": project["name"],
        "creator_id": current_user["id"],
        "creator_name": current_user["full_name"],
        "assignee_id": task_data.assignee_id,
        "assignee_name": assignee_name,
        "status": task_data.status.value,
        "priority": task_data.priority.value,
        "story_points": task_data.story_points,
        "due_date": task_data.due_date,
        "labels": task_data.labels,
        "parent_task_id": task_data.parent_task_id,
        "comment_count": 0,
        "status_history": [{"status": task_data.status.value, "changed_at": now, "changed_by": current_user["id"]}],
        "created_at": now,
        "updated_at": now,
    }
    
    result = await db.tasks.insert_one(task_doc)
    task_doc["id"] = str(result.inserted_id)
    
    # Update project task count
    await db.projects.update_one(
        {"_id": ObjectId(task_data.project_id)},
        {"$inc": {"task_count": 1}}
    )
    
    # Background: log activity
    background_tasks.add_task(
        log_activity, db, current_user["id"], task_data.project_id,
        "task_created", {"task_title": task_data.title, "task_id": task_doc["id"]}
    )
    
    return TaskResponse(**task_doc)


@router.get("/", response_model=PaginatedResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    List tasks with powerful filtering options.
    Supports filtering by project, assignee, status, priority, and search.
    """
    query = {}
    
    # Non-admins only see tasks from their projects
    if current_user["role"] != "admin":
        user_projects = await db.projects.distinct("_id", {"team_members": current_user["id"]})
        query["project_id"] = {"$in": [str(p) for p in user_projects]}
    
    if project_id:
        query["project_id"] = project_id
    if assignee_id:
        query["assignee_id"] = assignee_id
    if status_filter:
        query["status"] = status_filter
    if priority:
        query["priority"] = priority
    if search:
        query["$text"] = {"$search": search}
    if overdue_only:
        query["due_date"] = {"$lt": datetime.now(timezone.utc)}
        query["status"] = {"$ne": "done"}
    
    total = await db.tasks.count_documents(query)
    skip = (page - 1) * page_size
    
    cursor = db.tasks.find(query).sort([("priority", -1), ("created_at", -1)]).skip(skip).limit(page_size)
    tasks = await cursor.to_list(length=page_size)
    
    result = [TaskResponse(**{**t, "id": str(t["_id"])}) for t in tasks]
    
    return PaginatedResponse(
        data=result,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
        has_next=page * page_size < total,
        has_prev=page > 1
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get a single task by ID"""
    task = await _get_task_or_404(db, task_id)
    return TaskResponse(**{**task, "id": str(task["_id"])})


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    update_data: TaskUpdate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Update task fields.
    
    Status transitions are validated against the workflow state machine.
    For example, 'backlog' can only move to 'todo', not directly to 'done'.
    """
    task = await _get_task_or_404(db, task_id)
    
    update_fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    
    # Validate status transition
    if "status" in update_fields:
        new_status = update_fields["status"].value
        current_status = task["status"]
        allowed = VALID_TRANSITIONS.get(current_status, [])
        
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition: '{current_status}' → '{new_status}'. Allowed: {allowed}"
            )
        
        update_fields["status"] = new_status
        
        # Append to status history
        history_entry = {
            "status": new_status,
            "changed_at": datetime.now(timezone.utc),
            "changed_by": current_user["id"]
        }
        await db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$push": {"status_history": history_entry}}
        )
        
        # Update project completion stats if task completed
        if new_status == "done":
            await db.projects.update_one(
                {"_id": ObjectId(task["project_id"])},
                {"$inc": {"completed_task_count": 1}}
            )
            background_tasks.add_task(
                update_project_progress, db, task["project_id"]
            )
    
    if "priority" in update_fields and hasattr(update_fields["priority"], "value"):
        update_fields["priority"] = update_fields["priority"].value
    
    # Handle assignee update
    if "assignee_id" in update_fields and update_fields["assignee_id"]:
        assignee = await db.users.find_one({"_id": ObjectId(update_fields["assignee_id"])})
        if assignee:
            update_fields["assignee_name"] = assignee["full_name"]
    
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_fields})
    
    updated = await db.tasks.find_one({"_id": ObjectId(task_id)})
    return TaskResponse(**{**updated, "id": str(updated["_id"])})


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Delete a task. Only the creator or admin can delete."""
    task = await _get_task_or_404(db, task_id)
    
    if task["creator_id"] != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only the task creator or admin can delete this task")
    
    await db.tasks.delete_one({"_id": ObjectId(task_id)})
    await db.projects.update_one(
        {"_id": ObjectId(task["project_id"])},
        {"$inc": {"task_count": -1}}
    )


# ─── Comments ─────────────────────────────────────────────────────────────────

@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment(
    task_id: str,
    comment_data: CommentCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Add a comment to a task. Supports @mentions."""
    await _get_task_or_404(db, task_id)
    
    now = datetime.now(timezone.utc)
    comment_doc = {
        "task_id": task_id,
        "author_id": current_user["id"],
        "author_name": current_user["full_name"],
        "author_avatar": current_user.get("avatar_url"),
        "content": comment_data.content,
        "mentions": comment_data.mentions,
        "created_at": now,
        "updated_at": None,
    }
    
    result = await db.comments.insert_one(comment_doc)
    comment_doc["id"] = str(result.inserted_id)
    
    await db.tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$inc": {"comment_count": 1}}
    )
    
    return CommentResponse(**comment_doc)


@router.get("/{task_id}/comments", response_model=List[CommentResponse])
async def get_comments(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get all comments for a task, sorted by creation time"""
    comments = await db.comments.find({"task_id": task_id}).sort("created_at", 1).to_list(100)
    return [CommentResponse(**{**c, "id": str(c["_id"])}) for c in comments]


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_task_or_404(db, task_id: str) -> dict:
    try:
        task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def log_activity(db, user_id, project_id, action, details):
    """Background task: log user activity"""
    await db.activity_logs.insert_one({
        "user_id": user_id,
        "project_id": project_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now(timezone.utc)
    })


async def update_project_progress(db, project_id: str):
    """Background task: recalculate project progress percentage"""
    project = await db.projects.find_one({"_id": ObjectId(project_id)})
    if project and project.get("task_count", 0) > 0:
        progress = (project.get("completed_task_count", 0) / project["task_count"]) * 100
        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"progress_percent": round(progress, 1)}}
        )
