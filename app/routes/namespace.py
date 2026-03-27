from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.auth.rbac import require_role
from app.db import namespace_requests
from kubernetes import client
from app.k8s.loader import load_k8s_client
from bson import ObjectId
from app.db import clusters

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/namespaces")
def namespaces(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        return RedirectResponse("/clusters", status_code=302)

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        return RedirectResponse("/clusters", status_code=302)

    k8s = load_k8s_client(cluster.get("kubeconfig_path"))
    v1 = k8s.CoreV1Api()

    namespaces = v1.list_namespace().items

    return templates.TemplateResponse(
        "namespaces.html",
        {
            "request": request,
            "user": user,
            "namespaces": namespaces,
            "cluster": cluster,
        },
    )


@router.post("/namespace/request")
def request_namespace(
    request: Request,
    namespace: str = Form(...),
    cpu: str = Form(...),
    memory: str = Form(...),
    user=Depends(require_role(["admin", "view", "edit"])),
):
    cluster_id = request.session.get("active_cluster")

    if not cluster_id:
        return RedirectResponse("/clusters", status_code=302)

    namespace_requests.insert_one(
        {
            "cluster_id": cluster_id,
            "namespace": namespace,
            "cpu": cpu,
            "memory": memory,
            "requested_by": user["email"],
            "status": "pending",
        }
    )

    return RedirectResponse("/namespaces", status_code=302)
