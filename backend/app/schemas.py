"""
Pydantic schemas for request/response validation
Covers Users, Projects, Tasks, and Analytics
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
from bson import ObjectId


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Base Schema ──────────────────────────────────────────────────────────────

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(str(v)):
            raise ValueError("Invalid ObjectId")
        return str(v)


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.DEVELOPER

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ─── User Schemas ─────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    role: UserRole
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    skills: List[str] = []
    github_username: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    skills: Optional[List[str]] = None
    github_username: Optional[str] = None
    avatar_url: Optional[str] = None


# ─── Project Schemas ──────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    status: ProjectStatus = ProjectStatus.PLANNING
    tech_stack: List[str] = []
    repository_url: Optional[str] = None
    deadline: Optional[datetime] = None
    team_member_ids: List[str] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    tech_stack: Optional[List[str]] = None
    repository_url: Optional[str] = None
    deadline: Optional[datetime] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: ProjectStatus
    owner_id: str
    owner_name: str
    tech_stack: List[str]
    repository_url: Optional[str]
    deadline: Optional[datetime]
    team_members: List[dict]
    task_count: int = 0
    completed_task_count: int = 0
    progress_percent: float = 0.0
    created_at: datetime
    updated_at: datetime


# ─── Task Schemas ─────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5, max_length=5000)
    project_id: str
    assignee_id: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    story_points: Optional[int] = Field(None, ge=1, le=100)
    due_date: Optional[datetime] = None
    labels: List[str] = []
    parent_task_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    story_points: Optional[int] = Field(None, ge=1, le=100)
    due_date: Optional[datetime] = None
    labels: Optional[List[str]] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    project_id: str
    project_name: str
    creator_id: str
    creator_name: str
    assignee_id: Optional[str]
    assignee_name: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    story_points: Optional[int]
    due_date: Optional[datetime]
    labels: List[str]
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime


# ─── Comment Schemas ──────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    mentions: List[str] = []


class CommentResponse(BaseModel):
    id: str
    task_id: str
    author_id: str
    author_name: str
    author_avatar: Optional[str]
    content: str
    mentions: List[str]
    created_at: datetime
    updated_at: Optional[datetime]


# ─── Analytics Schemas ────────────────────────────────────────────────────────

class ProjectAnalytics(BaseModel):
    project_id: str
    project_name: str
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    progress_percent: float
    velocity: float  # story points per sprint
    team_size: int
    avg_task_completion_days: float
    tasks_by_priority: dict
    tasks_by_assignee: List[dict]
    burndown_data: List[dict]


class TeamAnalytics(BaseModel):
    total_developers: int
    active_projects: int
    tasks_completed_this_week: int
    avg_velocity: float
    top_contributors: List[dict]
    activity_heatmap: List[dict]


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    data: List
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
