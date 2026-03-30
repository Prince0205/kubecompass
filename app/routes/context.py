from fastapi import APIRouter, Request, Depends
from bson import ObjectId
from app.auth.rbac import require_role
from app.db import clusters
from app.k8s.loader import load_k8s_client
from pydantic import BaseModel
from app.routes.snapshot_service import snapshot_service


class ClusterSelect(BaseModel):
    cluster_id: str


class NamespaceSelect(BaseModel):
    namespace: str


router = APIRouter()


@router.get("/api/context")
def get_context(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    cluster_list = list(clusters.find({}, {"name": 1}))

    active_cluster = request.session.get("active_cluster")
    active_namespace = request.session.get("active_namespace")

    namespaces = []

    if active_cluster:
        cluster = clusters.find_one({"_id": ObjectId(active_cluster)})
        if cluster:
            k8s = load_k8s_client(cluster["kubeconfig_path"])
            v1 = k8s.CoreV1Api()
            namespaces = [ns.metadata.name for ns in v1.list_namespace().items]

    return {
        "clusters": [{"id": str(c["_id"]), "name": c["name"]} for c in cluster_list],
        "active_cluster": active_cluster,
        "namespaces": namespaces,
        "active_namespace": active_namespace,
        "user": {"email": user["email"], "role": user["role"]},
    }


@router.post("/api/context/cluster")
def set_cluster(
    payload: ClusterSelect,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    request.session["active_cluster"] = payload.cluster_id
    request.session.pop("active_namespace", None)

    # Notify snapshot service to watch this cluster
    snapshot_service.notify_namespace(payload.cluster_id, "default")

    return {"status": "ok"}


@router.post("/api/context/namespace")
def set_namespace(
    payload: NamespaceSelect,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    request.session["active_namespace"] = payload.namespace

    # Notify snapshot service to watch this namespace
    cluster_id = request.session.get("active_cluster")
    if cluster_id:
        ns = payload.namespace
        if ns and ns != "_all" and ns != "_all_":
            snapshot_service.notify_namespace(cluster_id, ns)
        else:
            # Watch all common namespaces
            for default_ns in [
                "default",
                "kube-system",
                "kube-public",
                "kube-node-lease",
            ]:
                snapshot_service.notify_namespace(cluster_id, default_ns)

    return {"status": "ok"}
