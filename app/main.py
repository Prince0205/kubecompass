from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.config import SECRET_KEY
from starlette.middleware.base import BaseHTTPMiddleware

import os
from app.auth.local import ensure_admin
from app.routes import (
    api_resources,
    api_v1,
    auth_api,
    context,
    crd_resources,
    deployments,
    metrics,
    namespace_requests,
    network_resources,
    nodes,
    pods,
    replicasets,
    storage_resources,
    workloads,
    config_resources,
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


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if (
            response.status_code == 404
            and not request.url.path.startswith("/api")
            and not request.url.path.startswith("/v1")
        ):
            return FileResponse("ui/dist/index.html")
        return response


app.add_middleware(SPAFallbackMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_api.router)
app.include_router(deployments.api_router)
app.include_router(api_resources.router)
app.include_router(api_v1.router)
app.include_router(context.router)
app.include_router(nodes.api_router)
app.include_router(pods.api_router)
app.include_router(replicasets.api_router)
app.include_router(metrics.router)
app.include_router(workloads.router)
app.include_router(config_resources.router)
app.include_router(network_resources.router)
app.include_router(storage_resources.router)
app.include_router(crd_resources.router)
app.include_router(namespace_requests.router)

app.mount("/", StaticFiles(directory="ui/dist", html=True), name="spa")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
