"""
Analytics API endpoints
MongoDB aggregation pipelines for project/team insights
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from typing import Optional

from app.security import get_current_user, require_manager_or_admin
from app.database import get_db

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Main dashboard analytics for the current user.
    Returns task counts, recent activity, and performance metrics.
    """
    user_id = current_user["id"]
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Tasks assigned to me
    my_tasks_pipeline = [
        {"$match": {"assignee_id": user_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    task_by_status = await db.tasks.aggregate(my_tasks_pipeline).to_list(10)
    
    # My tasks completed this week
    completed_this_week = await db.tasks.count_documents({
        "assignee_id": user_id,
        "status": "done",
        "updated_at": {"$gte": week_ago}
    })
    
    # Overdue tasks
    overdue = await db.tasks.count_documents({
        "assignee_id": user_id,
        "status": {"$nin": ["done"]},
        "due_date": {"$lt": now}
    })
    
    # My projects
    my_projects = await db.projects.count_documents({
        "team_members": user_id,
        "status": {"$in": ["active", "planning"]}
    })
    
    # Recent activity (last 10 actions)
    recent_activity = await db.activity_logs.find(
        {"user_id": user_id},
        {"action": 1, "details": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(10).to_list(10)
    
    # Task priority breakdown
    priority_pipeline = [
        {"$match": {"assignee_id": user_id, "status": {"$ne": "done"}}},
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
    ]
    priority_breakdown = await db.tasks.aggregate(priority_pipeline).to_list(5)
    
    return {
        "tasks_by_status": {item["_id"]: item["count"] for item in task_by_status},
        "completed_this_week": completed_this_week,
        "overdue_tasks": overdue,
        "active_projects": my_projects,
        "priority_breakdown": {item["_id"]: item["count"] for item in priority_breakdown},
        "recent_activity": [
            {
                "action": a["action"].replace("_", " ").title(),
                "details": a["details"],
                "timestamp": a["timestamp"].isoformat()
            }
            for a in recent_activity
        ]
    }


@router.get("/projects/{project_id}")
async def get_project_analytics(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Detailed analytics for a specific project.
    Includes burndown chart data, velocity, and contributor stats.
    """
    project = await db.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user["id"] not in project.get("team_members", []) and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Tasks by status
    status_pipeline = [
        {"$match": {"project_id": project_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "story_points": {"$sum": "$story_points"}}}
    ]
    status_data = await db.tasks.aggregate(status_pipeline).to_list(10)
    
    # Tasks by assignee (leaderboard)
    assignee_pipeline = [
        {"$match": {"project_id": project_id, "status": "done"}},
        {"$group": {
            "_id": "$assignee_id",
            "assignee_name": {"$first": "$assignee_name"},
            "completed_tasks": {"$sum": 1},
            "story_points": {"$sum": "$story_points"}
        }},
        {"$sort": {"completed_tasks": -1}},
        {"$limit": 10}
    ]
    contributors = await db.tasks.aggregate(assignee_pipeline).to_list(10)
    
    # Daily completion for burndown (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    burndown_pipeline = [
        {"$match": {
            "project_id": project_id,
            "status": "done",
            "updated_at": {"$gte": thirty_days_ago}
        }},
        {"$group": {
            "_id": {
                "year": {"$year": "$updated_at"},
                "month": {"$month": "$updated_at"},
                "day": {"$dayOfMonth": "$updated_at"}
            },
            "completed": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
    ]
    burndown_raw = await db.tasks.aggregate(burndown_pipeline).to_list(30)
    
    burndown_data = [
        {
            "date": f"{item['_id']['year']}-{item['_id']['month']:02d}-{item['_id']['day']:02d}",
            "completed": item["completed"]
        }
        for item in burndown_raw
    ]
    
    # Priority breakdown
    priority_pipeline = [
        {"$match": {"project_id": project_id}},
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
    ]
    priorities = await db.tasks.aggregate(priority_pipeline).to_list(5)
    
    total_tasks = project.get("task_count", 0)
    completed = project.get("completed_task_count", 0)
    
    return {
        "project_id": project_id,
        "project_name": project["name"],
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "progress_percent": project.get("progress_percent", 0),
        "tasks_by_status": {item["_id"]: item["count"] for item in status_data},
        "tasks_by_priority": {item["_id"]: item["count"] for item in priorities},
        "top_contributors": contributors,
        "burndown_data": burndown_data,
        "deadline": project.get("deadline"),
        "days_remaining": (project["deadline"] - datetime.now(timezone.utc)).days if project.get("deadline") else None
    }


@router.get("/team")
async def get_team_analytics(
    current_user: dict = Depends(require_manager_or_admin),
    db=Depends(get_db)
):
    """
    Team-wide analytics. Managers and admins only.
    
    Returns velocity, workload distribution, and productivity trends.
    """
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Active developers
    total_developers = await db.users.count_documents({"role": "developer", "is_active": True})
    
    # Active projects
    active_projects = await db.projects.count_documents({"status": "active"})
    
    # Tasks completed this week across all projects
    completed_this_week = await db.tasks.count_documents({
        "status": "done",
        "updated_at": {"$gte": week_ago}
    })
    
    # Workload distribution (open tasks per developer)
    workload_pipeline = [
        {"$match": {"status": {"$nin": ["done"]}, "assignee_id": {"$ne": None}}},
        {"$group": {
            "_id": "$assignee_id",
            "assignee_name": {"$first": "$assignee_name"},
            "open_tasks": {"$sum": 1},
            "critical_tasks": {
                "$sum": {"$cond": [{"$eq": ["$priority", "critical"]}, 1, 0]}
            }
        }},
        {"$sort": {"open_tasks": -1}}
    ]
    workload = await db.tasks.aggregate(workload_pipeline).to_list(20)
    
    # Activity heatmap (last 7 days)
    heatmap_pipeline = [
        {"$match": {"timestamp": {"$gte": week_ago}}},
        {"$group": {
            "_id": {
                "day": {"$dayOfWeek": "$timestamp"},
                "hour": {"$hour": "$timestamp"}
            },
            "activity_count": {"$sum": 1}
        }}
    ]
    heatmap = await db.activity_logs.aggregate(heatmap_pipeline).to_list(200)
    
    return {
        "total_developers": total_developers,
        "active_projects": active_projects,
        "tasks_completed_this_week": completed_this_week,
        "workload_distribution": workload,
        "activity_heatmap": [
            {
                "day": item["_id"]["day"],
                "hour": item["_id"]["hour"],
                "count": item["activity_count"]
            }
            for item in heatmap
        ]
    }
