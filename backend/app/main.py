"""
DevHub - Enterprise Developer Project Management Platform
FastAPI Backend with JWT Auth, RBAC, WebSockets, and REST API
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import logging
import uvicorn

from app.api import auth, projects, tasks, users, analytics, health
from app.database import init_db, close_db
from app.websocket_manager import ConnectionManager
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    logger.info("Starting DevHub API server...")
    await init_db()
    logger.info("Database initialized successfully")
    yield
    logger.info("Shutting down DevHub API server...")
    await close_db()


app = FastAPI(
    title="DevHub API",
    description="""
    ## DevHub - Enterprise Developer Platform API
    
    A full-featured project management system for development teams.
    
    ### Features
    - 🔐 JWT Authentication with refresh tokens
    - 👥 Role-based access control (Admin, Manager, Developer)
    - 📋 Project & Sprint management
    - ✅ Task tracking with priority and status
    - 📊 Analytics and reporting
    - 🔔 Real-time notifications via WebSockets
    - 🗄️ MongoDB for flexible document storage
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time notifications.
    Clients connect here to receive live updates on task assignments,
    project changes, and team activity.
    """
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast_to_user(user_id, f"Echo: {data}")
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        logger.info(f"User {user_id} disconnected from WebSocket")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
