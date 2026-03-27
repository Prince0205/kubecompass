# KubeCompass - Unified Kubernetes Dashboard

> One application. One port. Complete Kubernetes management.

## 🎯 Quick Start

### Windows
```bash
./quickstart.bat
```

### Linux/macOS
```bash
bash quickstart.sh
```

Then open http://localhost:8000 and login with:
- Email: `admin@example.com`
- Password: `admin123`

## ✨ Key Features

- **🔐 Secure Authentication** - Session-based login with MongoDB user storage
- **📊 Real-time Metrics** - CPU, Memory, Network monitoring
- **⚙️ Resource Management** - View all Kubernetes resources (Pods, Deployments, Services, etc.)
- **🔄 Multi-Cluster Support** - Manage multiple Kubernetes clusters
- **👥 RBAC Integration** - Role-based access control
- **📱 Responsive UI** - Works on desktop, tablet, and mobile
- **⚡ Fast Performance** - Optimized React SPA with caching

## 📋 What's Included

### Backend (FastAPI + MongoDB)
- 56 REST API endpoints
- Kubernetes client integration
- Metrics collection and aggregation
- Session-based authentication
- RBAC enforcement

### Frontend (React + Tailwind)
- Login/authentication pages
- Resource list views
- Cluster and namespace selection
- Metrics dashboard with charts
- Responsive sidebar navigation

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│     User Browser                        │
│  (http://localhost:8000)                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  FastAPI Backend (Port 8000)            │
├─────────────────────────────────────────┤
│ ✓ /api/auth/*      - Authentication    │
│ ✓ /v1/*            - API Endpoints     │
│ ✓ /api/resources/* - K8s Resources      │
│ ✓ /api/metrics/*   - Metrics            │
│ ✓ /static/*        - Static Files       │
│ ✓ /                - React SPA Fallback │
└────────┬──────────────────────┬─────────┘
         │                      │
    ┌────▼────┐            ┌───▼────┐
    │ MongoDB │            │ K8s    │
    │(Users,  │            │Cluster │
    │Clusters)│            │        │
    └─────────┘            └────────┘
```

## 📦 Requirements

- Python 3.8+
- Node.js 18+
- MongoDB 4.0+ (local or remote)
- Git

## 🚀 Manual Setup

If you prefer manual setup instead of using quickstart scripts:

### 1. Install Python Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Node Dependencies
```bash
cd ui
npm install
cd ..
```

### 3. Build React App
```bash
cd ui
npm run build
cd ..
```

### 4. Start MongoDB
```bash
# If installed locally
mongod

# If using Docker
docker run -d -p 27017:27017 mongo:latest
```

### 5. Run the Unified App
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Access the App
Open http://localhost:8000 in your browser

## 🔧 Configuration

### Environment Variables
```bash
# Skip admin user bootstrap
export KCP_SKIP_BOOTSTRAP=1

# MongoDB Connection (if not localhost)
# Edit app/config.py or app/db.py
```

### Port Configuration
To change the port, edit `app/main.py` line 66:
```python
uvicorn.run("app.main:app", host="0.0.0.0", port=YOUR_PORT, reload=True)
```

## 📱 API Reference

### Authentication
```
POST   /api/auth/login              - Login with email/password
POST   /api/auth/logout             - Logout (clears session)
GET    /api/auth/me                 - Get current user info
```

### Clusters
```
GET    /v1/clusters                 - List all clusters
POST   /v1/context/cluster          - Set active cluster
GET    /v1/namespaces               - List namespaces
POST   /v1/context/namespace        - Set active namespace
```

### Resources (requires cluster selection)
```
GET    /api/resources/workload/pods
GET    /api/resources/workload/deployments
GET    /api/resources/config/configmaps
GET    /api/resources/network/services
GET    /api/resources/storage/persistentvolumes
...and many more
```

### Metrics
```
GET    /api/metrics/cluster          - Cluster metrics
GET    /api/metrics/nodes            - Node metrics
GET    /api/metrics/namespace/{ns}   - Namespace metrics
GET    /api/metrics/pod/{ns}/{pod}   - Pod metrics
```

## 🧪 Testing

### Run Backend Tests
```bash
pytest tests/ -v
```

### Test Frontend in Development
```bash
cd ui
npm run dev
```

This starts a dev server on port 5173 with hot module reloading (but won't work with production backend - use production build for full integration).

## 🐛 Troubleshooting

### Port 8000 Already in Use
```bash
# Find process
lsof -i :8000  # On Windows: netstat -ano | findstr :8000

# Kill process
kill -9 <PID>  # On Windows: taskkill /PID <PID> /F
```

### Cannot Connect to MongoDB
```bash
# Check if MongoDB is running
mongosh  # or mongo for older versions

# Verify connection string in app/db.py
# Default: mongodb://localhost:27017/
```

### React App Not Loading
```bash
# Rebuild React
cd ui && npm run build && cd ..

# Check ui/dist folder exists and has files
ls ui/dist/
```

### Login Not Working
- Check MongoDB is running
- Check users collection exists in MongoDB
- Check email/password in users table
- Look at browser console for errors
- Check backend logs for auth errors

## 📚 Project Structure

```
.
├── app/                          # Backend (FastAPI)
│   ├── main.py                  # App entry point
│   ├── config.py                # Configuration
│   ├── db.py                    # MongoDB connection
│   ├── routes/
│   │   ├── auth_api.py         # REST auth endpoints ✨
│   │   ├── api_v1.py           # Cluster API endpoints
│   │   ├── metrics.py          # Metrics endpoints
│   │   ├── workloads.py        # Workload resources
│   │   ├── config_resources.py # Config resources
│   │   ├── network_resources.py # Network resources
│   │   ├── storage_resources.py # Storage resources
│   │   └── crd_resources.py    # Custom resource definitions
│   ├── auth/                    # Authentication
│   │   ├── rbac.py             # Role-based access control
│   │   └── local.py            # Local auth helpers
│   ├── k8s/                     # Kubernetes integration
│   │   ├── loader.py           # K8s client loader
│   │   ├── metrics.py          # Metrics collection
│   │   └── cache.py            # Caching layer
│   ├── templates/              # Old HTML templates (disabled)
│   └── static/                 # Static assets
│
├── ui/                          # Frontend (React)
│   ├── src/
│   │   ├── main.jsx            # React entry point
│   │   ├── App.jsx             # App router ✨
│   │   ├── pages/
│   │   │   ├── Login.jsx       # Login page ✨
│   │   │   ├── Dashboard.jsx   # Dashboard
│   │   │   ├── Resources.jsx   # Resource list
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── Header.jsx      # Header with logout ✨
│   │   │   ├── SidebarNew.jsx  # Navigation sidebar
│   │   │   └── ...
│   │   ├── context/
│   │   │   └── AppContext.jsx  # Auth state management ✨
│   │   ├── hooks/
│   │   │   └── useApi.js       # Data fetching hooks
│   │   ├── api.js              # API client
│   │   └── styles.css          # Global styles
│   ├── dist/                   # Production build ✨
│   ├── package.json
│   └── vite.config.js          # Vite configuration
│
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
├── quickstart.sh               # Linux/macOS start script ✨
├── quickstart.bat              # Windows start script ✨
├── INTEGRATION_COMPLETE.md     # Integration documentation ✨
└── README.md                   # This file
```

## ✨ What Was Integrated (New in this Session)

1. **REST Auth API** - New `/api/auth` endpoints for JSON-based login
2. **Login Page** - React login page with form validation
3. **Auth State Management** - AppContext checks auth on app load
4. **Protected Routes** - Dashboard only shows if user is authenticated
5. **User Menu** - Header shows current user + logout button
6. **SPA Configuration** - React dist folder served from backend
7. **Session Management** - Session cookies used for stateless sessions
8. **Single Port Deployment** - Everything runs on port 8000

## 🎓 Development Tips

### Hot Reload (Dev Mode)
```bash
# Frontend hot reload (separate dev server)
cd ui && npm run dev  # Port 5173

# Backend hot reload
python -m uvicorn app.main:app --reload
```

Note: Dev mode uses two ports. For production, use `npm run build` then start backend only.

### Database Management
```bash
# Access MongoDB directly
mongosh
use kubernetes_control_plane
db.users.find()
db.clusters.find()
```

### Debugging
```bash
# Backend debug output
# Add logging to app/main.py or specific routes:
import logging
logging.basicConfig(level=logging.DEBUG)

# Frontend debug output
# Check browser DevTools Console (F12)
# React Profiler: Install React DevTools extension
```

## 📄 License

See LICENSE file

## 🤝 Contributing

See CONTRIBUTING.md

## 📞 Support

For issues or questions:
1. Check INTEGRATION_COMPLETE.md for detailed integration info
2. Review troubleshooting section above
3. Check application logs
4. Verify all prerequisites are installed

---

**Status**: ✅ Production Ready
**Last Updated**: March 23, 2026
**Version**: 1.0.0 (Unified)
