# DevHub — Enterprise Developer Project Management Platform

> A full-stack Python web application for engineering teams to manage projects, track tasks, and monitor team performance in real-time.

![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![React](https://img.shields.io/badge/React-18-61dafb)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)

---

## 🏗️ Architecture

```
devhub/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── api/                # Route handlers (controllers)
│   │   │   ├── auth.py         # JWT auth: register, login, refresh
│   │   │   ├── projects.py     # Projects CRUD + team management
│   │   │   ├── tasks.py        # Tasks CRUD + comments + status machine
│   │   │   ├── analytics.py    # MongoDB aggregation pipelines
│   │   │   ├── users.py        # User profile management
│   │   │   └── health.py       # Health check endpoint
│   │   ├── main.py             # FastAPI app + WebSocket endpoint
│   │   ├── database.py         # Motor async MongoDB + indexes
│   │   ├── schemas.py          # Pydantic models + validation
│   │   ├── security.py         # JWT, bcrypt, RBAC dependencies
│   │   ├── config.py           # Pydantic settings (env vars)
│   │   └── websocket_manager.py
│   ├── tests/
│   │   └── test_api.py         # Pytest async test suite
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # React + Vite frontend
│   └── src/
│       ├── App.jsx             # Auth context, routing, all pages
│       └── index.css           # Dark developer design system
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # Full CI/CD pipeline
│
└── docker-compose.yml          # Full stack orchestration
```

## ✨ Features

### Backend
- **JWT Authentication** — Access tokens (30 min) + refresh tokens (7 days)
- **Role-Based Access Control** — Admin, Manager, Developer, Viewer roles
- **Task State Machine** — Validated status transitions (backlog → todo → in_progress → in_review → done)
- **MongoDB Aggregation Pipelines** — Analytics, burndown charts, velocity tracking
- **WebSocket Real-time** — Live task assignment notifications
- **Background Tasks** — FastAPI BackgroundTasks for async activity logging
- **Full-text Search** — MongoDB text indexes for projects/tasks
- **Pagination** — Cursor-based pagination on all list endpoints
- **OpenAPI Docs** — Auto-generated at `/api/docs`

### Frontend
- **React 18** with hooks and context API
- **JWT Auto-refresh** — Transparent token refresh on 401
- **Protected Routes** — Auth-gated navigation
- **Dashboard** — Real-time stats from analytics API
- **Kanban-style Task Filtering** — Filter by status, priority, project
- **Project Cards** — Progress bars, tech stack tags, team info

### DevOps
- **Docker Compose** — One-command local setup
- **GitHub Actions CI/CD** — Test → Security scan → Build → Deploy
- **Container Security** — Non-root Docker user
- **Health Checks** — Docker + API health endpoints

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
git clone https://github.com/yourusername/devhub.git
cd devhub
cp .env.example .env          # configure your secrets
docker compose up -d
```

App runs at:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

### Option 2: Local Development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env           # edit MongoDB URL, SECRET_KEY

# Start API server
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev                    # starts at http://localhost:5173
```

**Run Tests:**
```bash
# Backend
cd backend && pytest tests/ -v --cov=app

# Frontend
cd frontend && npm run test
```

---

## 📡 API Reference

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/register` | Register new user | Public |
| POST | `/api/v1/auth/login` | Login, get JWT tokens | Public |
| POST | `/api/v1/auth/refresh` | Refresh access token | Public |
| GET | `/api/v1/auth/me` | Get current user | Required |
| GET | `/api/v1/projects/` | List projects (paginated) | Required |
| POST | `/api/v1/projects/` | Create project | Manager+ |
| GET | `/api/v1/projects/{id}` | Get project details | Required |
| PUT | `/api/v1/projects/{id}` | Update project | Owner/Admin |
| GET | `/api/v1/tasks/` | List tasks with filters | Required |
| POST | `/api/v1/tasks/` | Create task | Required |
| PUT | `/api/v1/tasks/{id}` | Update task status | Required |
| POST | `/api/v1/tasks/{id}/comments` | Add comment | Required |
| GET | `/api/v1/analytics/dashboard` | Personal dashboard stats | Required |
| GET | `/api/v1/analytics/team` | Team analytics | Manager+ |
| WS | `/ws/{user_id}` | Real-time notifications | Token |

---

## 🔐 Environment Variables

```env
# .env
SECRET_KEY=your-super-secret-key-minimum-32-characters
MONGODB_URL=mongodb://localhost:27017
DB_NAME=devhub_db
REDIS_URL=redis://localhost:6379
ENVIRONMENT=development
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## 🧪 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API Framework | **FastAPI** | High-performance async REST API |
| Validation | **Pydantic v2** | Request/response schemas |
| Database | **MongoDB** (Motor) | Document storage, aggregations |
| Caching | **Redis** | Rate limiting, session cache |
| Auth | **JWT** (python-jose) | Stateless authentication |
| Passwords | **bcrypt** (passlib) | Secure password hashing |
| Real-time | **WebSockets** | Live notifications |
| Frontend | **React 18** + Vite | SPA with fast HMR |
| Routing | **React Router v6** | Client-side routing |
| Testing | **pytest** + **httpx** | Async API test suite |
| CI/CD | **GitHub Actions** | Automated test + deploy |
| Containers | **Docker** + Compose | Reproducible environments |

---

## 📝 Resume Description

> **DevHub — Full-Stack Developer Project Management Platform** *(Python, FastAPI, React, MongoDB)*
>
> Built an end-to-end enterprise web application for engineering teams featuring JWT authentication with RBAC, real-time WebSocket notifications, and a React dashboard. Implemented MongoDB aggregation pipelines for analytics and burndown charts. Designed a task state machine with validated status transitions. Containerized with Docker Compose and deployed via GitHub Actions CI/CD pipeline with automated testing and security scanning.

---

## 📄 License

MIT © 2024 — Built as a portfolio project
