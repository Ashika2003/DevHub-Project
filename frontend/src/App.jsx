import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom';

// ─── Auth Context ──────────────────────────────────────────────────────────

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchCurrentUser = async () => {
    try {
      const res = await api.get('/auth/me');
      setUser(res.data);
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token, refresh_token } = res.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    setToken(access_token);
    await fetchCurrentUser();
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

// ─── API Client ────────────────────────────────────────────────────────────

const BASE_URL = 'https://devhub-api-u7hz.onrender.com/api/v1';

const api = {
  async request(method, path, data = null) {
    const token = localStorage.getItem('access_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: data ? JSON.stringify(data) : null,
    });

    if (res.status === 401) {
      // Try refresh
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (refreshRes.ok) {
          const { access_token } = await refreshRes.json();
          localStorage.setItem('access_token', access_token);
          return api.request(method, path, data);
        }
      }
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Request failed');
    }

    return { data: await res.json(), status: res.status };
  },
  get: (path) => api.request('GET', path),
  post: (path, data) => api.request('POST', path, data),
  put: (path, data) => api.request('PUT', path, data),
  delete: (path) => api.request('DELETE', path),
};

// ─── Components ────────────────────────────────────────────────────────────

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  return user ? children : <Navigate to="/login" />;
}

function LoadingScreen() {
  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f0f23' }}>
      <div style={{ textAlign: 'center' }}>
        <div className="spinner" />
        <p style={{ color: '#7c85f3', marginTop: 16, fontFamily: 'monospace' }}>Loading DevHub...</p>
      </div>
    </div>
  );
}

// ─── Login Page ────────────────────────────────────────────────────────────

function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <span className="logo-icon">⬡</span>
          <span className="logo-text">DevHub</span>
        </div>
        <h1>Welcome back</h1>
        <p className="auth-subtitle">Sign in to your developer workspace</p>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="dev@company.com"
              required
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p className="auth-footer">
          No account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}

// ─── Sidebar ───────────────────────────────────────────────────────────────

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    { icon: '◈', label: 'Dashboard', path: '/dashboard' },
    { icon: '◉', label: 'Projects', path: '/projects' },
    { icon: '◷', label: 'My Tasks', path: '/tasks' },
    { icon: '◎', label: 'Analytics', path: '/analytics' },
    { icon: '◈', label: 'Team', path: '/team', adminOnly: true },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-icon">⬡</span>
        <span>DevHub</span>
      </div>

      <nav className="sidebar-nav">
        {navItems
          .filter(item => !item.adminOnly || ['admin', 'manager'].includes(user?.role))
          .map(item => (
            <Link key={item.path} to={item.path} className="nav-item">
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </Link>
          ))}
      </nav>

      <div className="sidebar-user">
        <div className="user-avatar">
          <img src={user?.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username}`} alt="avatar" />
        </div>
        <div className="user-info">
          <div className="user-name">{user?.full_name}</div>
          <div className="user-role">{user?.role}</div>
        </div>
        <button className="btn-icon" onClick={() => { logout(); navigate('/login'); }} title="Logout">⇥</button>
      </div>
    </aside>
  );
}

// ─── Dashboard ─────────────────────────────────────────────────────────────

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    api.get('/analytics/dashboard')
      .then(res => setStats(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const taskStatuses = stats?.tasks_by_status || {};
  const totalTasks = Object.values(taskStatuses).reduce((a, b) => a + b, 0);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Good morning, {user?.full_name?.split(' ')[0]} 👋</h1>
          <p className="text-muted">Here's what's happening in your workspace</p>
        </div>
      </div>

      {loading ? (
        <div className="loading-pulse">Loading stats...</div>
      ) : (
        <>
          <div className="stats-grid">
            <StatCard icon="✓" label="Completed This Week" value={stats?.completed_this_week || 0} color="#22d3a5" />
            <StatCard icon="⚡" label="Active Projects" value={stats?.active_projects || 0} color="#7c85f3" />
            <StatCard icon="◷" label="Open Tasks" value={totalTasks} color="#f59e0b" />
            <StatCard icon="⚠" label="Overdue" value={stats?.overdue_tasks || 0} color="#f87171" />
          </div>

          <div className="dashboard-grid">
            <div className="card">
              <h3>Tasks by Status</h3>
              <div className="status-bars">
                {Object.entries(taskStatuses).map(([status, count]) => (
                  <div key={status} className="status-bar-row">
                    <span className="status-label">{status.replace('_', ' ')}</span>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{
                          width: totalTasks ? `${(count / totalTasks) * 100}%` : '0%',
                          background: STATUS_COLORS[status] || '#7c85f3'
                        }}
                      />
                    </div>
                    <span className="bar-count">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <h3>Recent Activity</h3>
              <div className="activity-list">
                {(stats?.recent_activity || []).slice(0, 6).map((act, i) => (
                  <div key={i} className="activity-item">
                    <div className="activity-dot" />
                    <div>
                      <div className="activity-action">{act.action}</div>
                      <div className="activity-time">{new Date(act.timestamp).toLocaleDateString()}</div>
                    </div>
                  </div>
                ))}
                {(!stats?.recent_activity?.length) && (
                  <p className="text-muted" style={{ padding: '1rem' }}>No recent activity yet</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, color }) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ color }}>{icon}</div>
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

const STATUS_COLORS = {
  backlog: '#6b7280',
  todo: '#7c85f3',
  in_progress: '#f59e0b',
  in_review: '#8b5cf6',
  done: '#22d3a5',
};

// ─── Projects Page ─────────────────────────────────────────────────────────

function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const res = await api.get('/projects/?page_size=50');
      setProjects(res.data.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Projects</h1>
          <p className="text-muted">{projects.length} projects in your workspace</p>
        </div>
        {['admin', 'manager'].includes(user?.role) && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New Project
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading-pulse">Loading projects...</div>
      ) : (
        <div className="projects-grid">
          {projects.map(p => <ProjectCard key={p.id} project={p} />)}
          {!projects.length && (
            <div className="empty-state">
              <p>No projects yet. Create your first project!</p>
            </div>
          )}
        </div>
      )}

      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadProjects(); }}
        />
      )}
    </div>
  );
}

function ProjectCard({ project }) {
  const statusColors = {
    active: '#22d3a5', planning: '#7c85f3',
    on_hold: '#f59e0b', completed: '#6b7280', archived: '#374151'
  };

  return (
    <Link to={`/projects/${project.id}`} className="project-card">
      <div className="project-card-header">
        <span className="project-status" style={{ background: statusColors[project.status] + '22', color: statusColors[project.status] }}>
          {project.status.replace('_', ' ')}
        </span>
        <span className="project-date">{new Date(project.created_at).toLocaleDateString()}</span>
      </div>
      <h3 className="project-name">{project.name}</h3>
      <p className="project-desc">{project.description.slice(0, 100)}...</p>

      <div className="project-progress">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${project.progress_percent}%` }} />
        </div>
        <span>{project.progress_percent}%</span>
      </div>

      <div className="project-footer">
        <div className="tech-tags">
          {project.tech_stack?.slice(0, 3).map(t => <span key={t} className="tag">{t}</span>)}
        </div>
        <span className="text-muted">{project.task_count} tasks</span>
      </div>
    </Link>
  );
}

function CreateProjectModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', description: '', tech_stack: '', status: 'planning' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/projects/', {
        ...form,
        tech_stack: form.tech_stack.split(',').map(s => s.trim()).filter(Boolean)
      });
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>New Project</h2>
          <button className="btn-icon" onClick={onClose}>✕</button>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Project Name</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="My Awesome Project" required />
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="What does this project do?" required rows={3} />
          </div>
          <div className="form-group">
            <label>Tech Stack (comma separated)</label>
            <input value={form.tech_stack} onChange={e => setForm({ ...form, tech_stack: e.target.value })} placeholder="Python, FastAPI, React, MongoDB" />
          </div>
          <div className="form-group">
            <label>Status</label>
            <select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}>
              <option value="planning">Planning</option>
              <option value="active">Active</option>
            </select>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Tasks Page ────────────────────────────────────────────────────────────

function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    loadTasks();
  }, [filter]);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const statusParam = filter !== 'all' ? `&status=${filter}` : '';
      const res = await api.get(`/tasks/?assignee_id=${user?.id}${statusParam}&page_size=50`);
      setTasks(res.data.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const FILTERS = ['all', 'todo', 'in_progress', 'in_review', 'done'];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>My Tasks</h1>
          <p className="text-muted">{tasks.length} tasks assigned to you</p>
        </div>
      </div>

      <div className="filter-tabs">
        {FILTERS.map(f => (
          <button
            key={f}
            className={`filter-tab ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f.replace('_', ' ')}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-pulse">Loading tasks...</div>
      ) : (
        <div className="tasks-list">
          {tasks.map(task => <TaskRow key={task.id} task={task} onUpdate={loadTasks} />)}
          {!tasks.length && (
            <div className="empty-state">
              <p>No tasks found. You're all caught up! 🎉</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TaskRow({ task, onUpdate }) {
  const priorityColors = {
    low: '#6b7280', medium: '#7c85f3', high: '#f59e0b', critical: '#f87171'
  };

  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'done';

  return (
    <div className={`task-row ${isOverdue ? 'overdue' : ''}`}>
      <div className="task-priority-dot" style={{ background: priorityColors[task.priority] }} />
      <div className="task-main">
        <div className="task-title">{task.title}</div>
        <div className="task-meta">
          <span className="tag">{task.project_name}</span>
          {task.due_date && (
            <span className={`due-date ${isOverdue ? 'overdue-text' : ''}`}>
              Due {new Date(task.due_date).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
      <div className="task-status">
        <span
          className="status-badge"
          style={{ background: STATUS_COLORS[task.status] + '22', color: STATUS_COLORS[task.status] }}
        >
          {task.status.replace('_', ' ')}
        </span>
      </div>
      <div className="task-points">
        {task.story_points && <span className="points-badge">{task.story_points} pts</span>}
      </div>
    </div>
  );
}

// ─── Analytics Page ────────────────────────────────────────────────────────

function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [teamData, setTeamData] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    api.get('/analytics/dashboard').then(res => setData(res.data)).catch(console.error);
    if (['admin', 'manager'].includes(user?.role)) {
      api.get('/analytics/team').then(res => setTeamData(res.data)).catch(console.error);
    }
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Analytics</h1>
        <p className="text-muted">Performance insights for your team</p>
      </div>

      {data && (
        <div className="analytics-grid">
          <div className="card">
            <h3>Priority Breakdown</h3>
            <div className="priority-chart">
              {Object.entries(data.priority_breakdown || {}).map(([p, count]) => (
                <div key={p} className="priority-item">
                  <div className="priority-ring" style={{ '--pct': `${count * 10}%` }}>
                    <span>{count}</span>
                  </div>
                  <span className="priority-name">{p}</span>
                </div>
              ))}
            </div>
          </div>

          {teamData && (
            <div className="card">
              <h3>Team Workload</h3>
              <div className="workload-list">
                {(teamData.workload_distribution || []).slice(0, 8).map((w, i) => (
                  <div key={i} className="workload-item">
                    <span className="workload-name">{w.assignee_name || 'Unassigned'}</span>
                    <div className="workload-bar-track">
                      <div className="workload-bar" style={{ width: `${Math.min(w.open_tasks * 10, 100)}%` }} />
                    </div>
                    <span className="workload-count">{w.open_tasks}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main App ──────────────────────────────────────────────────────────────

function AppLayout({ children }) {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/dashboard" />} />
          <Route path="/dashboard" element={
            <PrivateRoute><AppLayout><Dashboard /></AppLayout></PrivateRoute>
          } />
          <Route path="/projects" element={
            <PrivateRoute><AppLayout><ProjectsPage /></AppLayout></PrivateRoute>
          } />
          <Route path="/tasks" element={
            <PrivateRoute><AppLayout><TasksPage /></AppLayout></PrivateRoute>
          } />
          <Route path="/analytics" element={
            <PrivateRoute><AppLayout><AnalyticsPage /></AppLayout></PrivateRoute>
          } />
        </Routes>
      </AuthProvider>
    </Router>
  );
}
