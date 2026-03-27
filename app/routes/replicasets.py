from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from kubernetes import client

from app.auth.session import get_current_user
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId

ui_router = APIRouter()
api_router = APIRouter(prefix="/api/resources/replicasets")
templates = Jinja2Templates(directory="app/templates")

def get_context(request: Request):
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace")

    if not cluster_id or not namespace:
        raise HTTPException(400, "Cluster or namespace not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])
    return k8s, namespace

@ui_router.get("/replicasets", response_class=HTMLResponse)
def replicasets_page(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    return templates.TemplateResponse(
        "replicasets.html",
        {
            "request": request,
            "user": user
        }
    )

@api_router.get("/{name}")
def replicaset_details(
    name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()
    v1 = k8s.CoreV1Api()

    rs = apps.read_namespaced_replica_set(name, namespace)

    # ----- selector -----
    selector = rs.spec.selector.match_labels or {}
    label_selector = ",".join(f"{k}={v}" for k, v in selector.items())

    pods = v1.list_namespaced_pod(
        namespace,
        label_selector=label_selector
    ).items

    # ----- SAFE owner extraction (IMPORTANT) -----
    owner = None
    if rs.metadata.owner_references:
        for o in rs.metadata.owner_references:
            if o.kind == "Deployment":
                owner = o.name
                break

    return {
        "name": rs.metadata.name,
        "replicas": {
            "desired": rs.spec.replicas or 0,
            "ready": rs.status.ready_replicas or 0,
            "available": rs.status.available_replicas or 0
        },
        "owner": owner,
        "images": [
            c.image for c in rs.spec.template.spec.containers
        ],
        "selector": selector,
        "pods": [
            {
                "name": p.metadata.name,
                "status": p.status.phase
            }
            for p in pods
        ]
    }