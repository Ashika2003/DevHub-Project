"""
Test suite for DevHub API
Tests authentication, project CRUD, and task management
Run with: pytest tests/ -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Auth Tests ───────────────────────────────────────────────────────────────

class TestAuthentication:
    
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """Test successful user registration"""
        response = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "SecurePass123",
            "full_name": "Test User",
            "role": "developer"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "password" not in data  # Password must never be returned
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, existing_user):
        """Test that duplicate email registration fails"""
        response = await client.post("/api/v1/auth/register", json={
            "email": existing_user["email"],
            "username": "differentuser",
            "password": "SecurePass123",
            "full_name": "Another User"
        })
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, existing_user):
        """Test successful login returns tokens"""
        response = await client.post("/api/v1/auth/login", json={
            "email": existing_user["email"],
            "password": existing_user["plain_password"]
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, existing_user):
        """Test login with wrong password returns 401"""
        response = await client.post("/api/v1/auth/login", json={
            "email": existing_user["email"],
            "password": "WrongPassword123"
        })
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client, auth_headers):
        """Test /me endpoint with valid token"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "role" in data
    
    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client):
        """Test /me endpoint without token returns 403"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_weak_password_rejected(self, client):
        """Test that weak passwords are rejected at schema level"""
        response = await client.post("/api/v1/auth/register", json={
            "email": "weak@test.com",
            "username": "weakuser",
            "password": "simple",  # No uppercase, no digit
            "full_name": "Weak User"
        })
        assert response.status_code == 422  # Validation error


# ─── Project Tests ────────────────────────────────────────────────────────────

class TestProjects:
    
    @pytest.mark.asyncio
    async def test_create_project_as_manager(self, client, manager_headers):
        """Managers can create projects"""
        response = await client.post("/api/v1/projects/", 
            headers=manager_headers,
            json={
                "name": "My Test Project",
                "description": "A project created during testing for our CI pipeline",
                "status": "planning",
                "tech_stack": ["Python", "FastAPI", "MongoDB"]
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Test Project"
        assert "Python" in data["tech_stack"]
    
    @pytest.mark.asyncio
    async def test_create_project_as_developer_forbidden(self, client, auth_headers):
        """Developers cannot create projects"""
        response = await client.post("/api/v1/projects/",
            headers=auth_headers,
            json={
                "name": "Unauthorized Project",
                "description": "This should not be created by a developer role",
            }
        )
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_list_projects_paginated(self, client, auth_headers):
        """Test project listing with pagination"""
        response = await client.get(
            "/api/v1/projects/?page=1&page_size=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert "total_pages" in data


# ─── Task Tests ───────────────────────────────────────────────────────────────

class TestTasks:
    
    @pytest.mark.asyncio
    async def test_invalid_status_transition(self, client, auth_headers, existing_task):
        """Test that invalid status transitions are rejected"""
        # Try to go from 'backlog' directly to 'done' (not allowed)
        response = await client.put(
            f"/api/v1/tasks/{existing_task['id']}",
            headers=auth_headers,
            json={"status": "done"}
        )
        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_valid_status_transition(self, client, auth_headers, existing_task):
        """Test that valid status transitions succeed"""
        # backlog -> todo (valid)
        response = await client.put(
            f"/api/v1/tasks/{existing_task['id']}",
            headers=auth_headers,
            json={"status": "todo"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "todo"
    
    @pytest.mark.asyncio
    async def test_add_comment(self, client, auth_headers, existing_task):
        """Test adding a comment to a task"""
        response = await client.post(
            f"/api/v1/tasks/{existing_task['id']}/comments",
            headers=auth_headers,
            json={"content": "This is a test comment @alice"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "This is a test comment @alice"


# ─── Security Tests ───────────────────────────────────────────────────────────

class TestSecurity:
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client):
        """Expired tokens should return 401"""
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired"
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio  
    async def test_admin_endpoint_requires_admin(self, client, auth_headers):
        """Admin-only endpoints reject non-admin users"""
        response = await client.get("/api/v1/users/", headers=auth_headers)
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_sql_injection_in_search(self, client, auth_headers):
        """Test that search inputs are safely handled"""
        response = await client.get(
            '/api/v1/tasks/?search=\' OR 1=1; DROP TABLE tasks;--',
            headers=auth_headers
        )
        # Should return 200 with empty/safe results, not crash
        assert response.status_code in [200, 422]
