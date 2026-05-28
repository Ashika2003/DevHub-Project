"""
WebSocket Connection Manager
Handles real-time notifications and live updates
"""

from fastapi import WebSocket
from typing import Dict
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.
    Supports user-specific and broadcast messaging.
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected. Active: {len(self.active_connections)}")
        
        # Send welcome message
        await self.broadcast_to_user(user_id, json.dumps({
            "type": "connected",
            "message": "Connected to DevHub real-time updates"
        }))
    
    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        logger.info(f"User {user_id} disconnected. Active: {len(self.active_connections)}")
    
    async def broadcast_to_user(self, user_id: str, message: str):
        """Send message to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
                self.disconnect(user_id)
    
    async def broadcast_to_project(self, project_id: str, message: dict, db):
        """Send message to all members of a project"""
        project = await db.projects.find_one({"_id": project_id})
        if project:
            for member_id in project.get("team_members", []):
                await self.broadcast_to_user(member_id, json.dumps(message))
    
    async def broadcast_all(self, message: str):
        """Broadcast to all connected users"""
        disconnected = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(user_id)
        
        for user_id in disconnected:
            self.disconnect(user_id)
    
    @property
    def connected_count(self) -> int:
        return len(self.active_connections)
