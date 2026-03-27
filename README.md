# KubeCompass - Kubernetes Dashboard

A unified Kubernetes management dashboard for managing multiple clusters from a single interface.

## Features

- **Multi-cluster Management**: Connect to multiple Kubernetes clusters
- **Resource Management**: View and manage Pods, Deployments, Services, ConfigMaps, Secrets, and more
- **Namespace Management**: Create and manage namespaces
- **Metrics Dashboard**: View CPU and memory usage
- **User Authentication**: Secure login with MongoDB user storage

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- MongoDB 4.0+

### Windows

```bash
.\quickstart.bat
```

### Linux/macOS

```bash
bash quickstart.sh
```

Then open http://localhost:8000

### Manual Setup

1. **Install Python dependencies:**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

2. **Install Node dependencies and build:**
```bash
cd ui
npm install
npm run build
cd ..
```

3. **Start MongoDB** (required):
```bash
mongod
```

4. **Start the backend:**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. **Open browser:** http://localhost:8000

### Default Credentials

- Email: `admin@example.com`
- Password: `admin123`

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT License - see LICENSE file
