from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from bson import ObjectId

from app.auth.rbac import require_role
from app.db import clusters
from app.k8s.loader import load_k8s_client
from app.k8s.discovery import discover_resources

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/resources/{namespace}")
def view_resources(
    namespace: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    cluster_id = request.session.get("active_cluster")
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})

    k8s = load_k8s_client(cluster["kubeconfig_path"])
    data = discover_resources(k8s, namespace)

    return templates.TemplateResponse(
        "resources.html",
        {
            "request": request,
            "user": user,
            "namespace": namespace,
            "resources": data
        }
    )
