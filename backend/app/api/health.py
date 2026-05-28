"""Health check endpoint"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from app.database import get_db

router = APIRouter()

@router.get("/health")
async def health_check(db=Depends(get_db)):
    """System health check — used by load balancers and monitoring"""
    try:
        await db.command("ping")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "version": "1.0.0"
    }
