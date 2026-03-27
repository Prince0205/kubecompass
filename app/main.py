from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.config import SECRET_KEY
from starlette.middleware.base import BaseHTTPMiddleware

import os
from app.auth.local import ensure_admin
from app.routes import (
    auth,
    dashboard,
    namespace,
    clusters,
    admin,
    resources,
    api_resources,
    context,
    nodes,
    cluster_overview,
    ui_cluster,
    pods,
    deployments,
    replicasets,
    api_v1,
    resource_page,
    metrics,
    workloads,
    config_resources,
    network_resources,
    storage_resources,
    crd_resources,
    auth_api,
    namespace_requests,
)

if os.getenv("KCP_SKIP_BOOTSTRAP") != "1":
    ensure_admin()

app = FastAPI(title="Kubernetes Control Plane")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


# SPA Fallback middleware - serve index.html for all non-API routes
class SPAFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # If 404 and not an API route, serve index.html
        if (
            response.status_code == 404
            and not request.url.path.startswith("/api")
            and not request.url.path.startswith("/v1")
        ):
            return FileResponse("ui/dist/index.html")
        return response


app.add_middleware(SPAFallbackMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Register REST API auth routes
app.include_router(auth_api.router)

# Note: Commenting out old HTML template routes to use React SPA only
# These routes serve HTML templates that conflict with React SPA
# app.include_router(auth.router)
# app.include_router(dashboard.router)
# app.include_router(namespace.router)  # Use React Namespaces page instead
# app.include_router(clusters.router)   # Use React Clusters page instead
# app.include_router(admin.router)
# app.include_router(resources.router)
# Deployment-specific routes (API only)
app.include_router(deployments.api_router)
# Comment: deployments.ui_router serves HTML template, not needed for React SPA
# app.include_router(deployments.ui_router)
app.include_router(api_resources.router)
app.include_router(api_v1.router)
app.include_router(context.router)
# Comment: Old UI routers serve HTML templates, not needed for React SPA
# app.include_router(resource_page.ui_router)
# app.include_router(nodes.ui_router)
app.include_router(nodes.api_router)
# app.include_router(cluster_overview.router)
# app.include_router(ui_cluster.router)
# app.include_router(pods.ui_router)
app.include_router(pods.api_router)
# app.include_router(replicasets.ui_router)
app.include_router(replicasets.api_router)
app.include_router(metrics.router)
app.include_router(workloads.router)
app.include_router(config_resources.router)
app.include_router(network_resources.router)
app.include_router(storage_resources.router)
app.include_router(crd_resources.router)
app.include_router(namespace_requests.router)

# Mount React SPA dist folder
app.mount("/", StaticFiles(directory="ui/dist", html=True), name="spa")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
