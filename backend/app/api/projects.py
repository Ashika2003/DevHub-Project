"""
Projects API endpoints
Full CRUD with pagination, filtering, search, and team management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from math import ceil

from app.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, PaginatedResponse
)
from app.security import get_current_user, require_manager_or_admin
from app.database import get_db

router = APIRouter()


def serialize_project(doc: dict, owner: dict = None, members: list = None) -> dict:
    """Convert MongoDB document to API response dict"""
    doc["id"] = str(doc["_id"])
    doc["owner_name"] = owner.get("full_name", "Unknown") if owner else "Unknown"
    doc["team_members"] = members or []
    return doc


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: dict = Depends(require_manager_or_admin),
    db=Depends(get_db)
):
    """
    Create a new project. Requires Manager or Admin role.
    
    The creator is automatically set as the project owner.
    """
    now = datetime.now(timezone.utc)
    
    # Validate team member IDs
    valid_members = []
    for member_id in project_data.team_member_ids:
        try:
            member = await db.users.find_one({"_id": ObjectId(member_id)})
            if member:
                valid_members.append(member_id)
        except Exception:
            pass
    
    project_doc = {
        "name": project_data.name,
        "description": project_data.description,
        "status": project_data.status.value,
        "owner_id": current_user["id"],
        "tech_stack": project_data.tech_stack,
        "repository_url": project_data.repository_url,
        "deadline": project_data.deadline,
        "team_members": list(set(valid_members + [current_user["id"]])),
        "task_count": 0,
        "completed_task_count": 0,
        "progress_percent": 0.0,
        "created_at": now,
        "updated_at": now,
    }
    
    result = await db.projects.insert_one(project_doc)
    project_doc["id"] = str(result.inserted_id)
    
    # Log activity
    await db.activity_logs.insert_one({
        "user_id": current_user["id"],
        "project_id": project_doc["id"],
        "action": "project_created",
        "details": {"project_name": project_data.name},
        "timestamp": now
    })
    
    members_data = await _get_members_data(db, project_doc["team_members"])
    return serialize_project(project_doc, current_user, members_data)


@router.get("/", response_model=PaginatedResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    my_projects: bool = Query(False, description="Only show my projects"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    List all accessible projects with filtering and pagination.
    
    - Admins see all projects
    - Others see only projects they're members of
    """
    query = {}
    
    # Access control: non-admins see only their projects
    if current_user["role"] != "admin" or my_projects:
        query["team_members"] = current_user["id"]
    
    if status:
        query["status"] = status
    
    if search:
        query["$text"] = {"$search": search}
    
    total = await db.projects.count_documents(query)
    skip = (page - 1) * page_size
    
    cursor = db.projects.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    projects = await cursor.to_list(length=page_size)
    
    # Enrich with owner and member data
    result = []
    for project in projects:
        owner = await db.users.find_one({"_id": ObjectId(project["owner_id"])})
        members_data = await _get_members_data(db, project.get("team_members", []))
        result.append(serialize_project(project, owner, members_data))
    
    return PaginatedResponse(
        data=result,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 0,
        has_next=page * page_size < total,
        has_prev=page > 1
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get a single project by ID"""
    project = await _get_project_or_404(db, project_id, current_user)
    owner = await db.users.find_one({"_id": ObjectId(project["owner_id"])})
    members_data = await _get_members_data(db, project.get("team_members", []))
    return serialize_project(project, owner, members_data)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    update_data: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Update a project. Only the owner or admin can update.
    """
    project = await _get_project_or_404(db, project_id, current_user)
    
    # Check ownership
    if project["owner_id"] != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner or admin can update this project"
        )
    
    update_fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if update_fields:
        if "status" in update_fields:
            update_fields["status"] = update_fields["status"].value
        update_fields["updated_at"] = datetime.now(timezone.utc)
        
        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": update_fields}
        )
    
    updated = await db.projects.find_one({"_id": ObjectId(project_id)})
    owner = await db.users.find_one({"_id": ObjectId(updated["owner_id"])})
    members_data = await _get_members_data(db, updated.get("team_members", []))
    return serialize_project(updated, owner, members_data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: dict = Depends(require_manager_or_admin),
    db=Depends(get_db)
):
    """
    Soft-delete a project by setting status to archived.
    Hard delete requires admin role.
    """
    project = await _get_project_or_404(db, project_id, current_user)
    
    if project["owner_id"] != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status": "archived", "updated_at": datetime.now(timezone.utc)}}
    )


@router.post("/{project_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def add_team_member(
    project_id: str,
    user_id: str,
    current_user: dict = Depends(require_manager_or_admin),
    db=Depends(get_db)
):
    """Add a user to the project team"""
    project = await _get_project_or_404(db, project_id, current_user)
    
    # Verify user exists
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$addToSet": {"team_members": user_id}}
    )
    
    return {"message": f"User {user['full_name']} added to project"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_project_or_404(db, project_id: str, current_user: dict) -> dict:
    """Fetch project or raise 404, with access check"""
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Non-admins can only access their own projects
    if current_user["role"] != "admin":
        if current_user["id"] not in project.get("team_members", []):
            raise HTTPException(status_code=403, detail="Access denied to this project")
    
    return project


async def _get_members_data(db, member_ids: list) -> list:
    """Fetch basic info for a list of user IDs"""
    members = []
    for uid in member_ids:
        try:
            user = await db.users.find_one(
                {"_id": ObjectId(uid)},
                {"full_name": 1, "username": 1, "avatar_url": 1, "role": 1}
            )
            if user:
                members.append({
                    "id": str(user["_id"]),
                    "full_name": user["full_name"],
                    "username": user["username"],
                    "avatar_url": user.get("avatar_url"),
                    "role": user["role"]
                })
        except Exception:
            pass
    return members
