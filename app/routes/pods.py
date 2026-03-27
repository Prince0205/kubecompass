from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth.rbac import require_role
from app.db import clusters
from bson import ObjectId
from app.k8s.loader import load_k8s_client
import yaml

ui_router = APIRouter()
api_router = APIRouter(prefix="/api/resources/pods")
templates = Jinja2Templates(directory="app/templates")


def get_context(request):
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace")

    if not cluster_id or not namespace:
        raise HTTPException(400, "Cluster or namespace not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])

    return k8s, namespace


@ui_router.get("/pods", response_class=HTMLResponse)
def pods_page(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    return templates.TemplateResponse("pods.html", {"request": request, "user": user})


@api_router.get("/{pod_name}")
def pod_details(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    pod = v1.read_namespaced_pod(pod_name, namespace)

    return {
        "name": pod.metadata.name,
        "namespace": namespace,
        "node": pod.spec.node_name,
        "status": pod.status.phase,
        "containers": [c.name for c in pod.spec.containers],
        "images": [c.image for c in pod.spec.containers],
        "restarts": sum(
            cs.restart_count for cs in (pod.status.container_statuses or [])
        ),
    }


@api_router.get("/{pod_name}/events")
def pod_events(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    events = v1.list_namespaced_event(namespace).items

    return [
        {
            "type": e.type,
            "reason": e.reason,
            "message": e.message,
            "time": e.last_timestamp or e.event_time,
        }
        for e in events
        if e.involved_object
        and e.involved_object.kind == "Pod"
        and e.involved_object.name == pod_name
    ]


@api_router.get("/{pod_name}/logs")
def pod_logs(
    pod_name: str,
    request: Request,
    container: str = Query(None),
    tail: int = Query(200),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    logs = v1.read_namespaced_pod_log(
        name=pod_name, namespace=namespace, container=container, tail_lines=tail
    )

    return {"logs": logs}


@api_router.delete("/{pod_name}")
def delete_pod(
    pod_name: str, request: Request, user=Depends(require_role(["admin", "edit"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    v1.delete_namespaced_pod(name=pod_name, namespace=namespace)

    return {"status": "deleted"}


@api_router.get("/{pod_name}/yaml")
def pod_yaml(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    pod = v1.read_namespaced_pod(pod_name, namespace)

    # Remove runtime-only fields
    pod.metadata.managed_fields = None
    pod.metadata.resource_version = None
    pod.metadata.uid = None
    pod.metadata.creation_timestamp = None
    pod.status = None

    return {"yaml": yaml.safe_dump(pod.to_dict(), sort_keys=False), "editable": False}
