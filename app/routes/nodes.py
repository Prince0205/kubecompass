from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from bson import ObjectId
from datetime import datetime, timezone

from app.auth.rbac import require_role
from app.db import clusters, audit_logs
from app.k8s.loader import load_k8s_client

templates = Jinja2Templates(directory="app/templates")

# UI ROUTER (no prefix)
ui_router = APIRouter()

# API ROUTER
api_router = APIRouter(prefix="/api/resources")


@ui_router.get("/nodes", response_class=HTMLResponse)
def nodes_page(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    return templates.TemplateResponse("nodes.html", {"request": request, "user": user})


@api_router.get("/nodes")
def list_nodes(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "Cluster not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])
    v1 = k8s.CoreV1Api()

    result = []

    for node in v1.list_node().items:
        conditions = {c.type: c.status for c in node.status.conditions or []}
        status = "Ready" if conditions.get("Ready") == "True" else "NotReady"

        if node.spec.unschedulable:
            status += ",SchedulingDisabled"

        labels = node.metadata.labels or {}
        roles = [
            k.replace("node-role.kubernetes.io/", "")
            for k in labels
            if k.startswith("node-role.kubernetes.io/")
        ]
        role = ",".join(roles) if roles else "worker"

        created = node.metadata.creation_timestamp
        age_days = (datetime.now(timezone.utc) - created).days

        result.append(
            {
                "name": node.metadata.name,
                "status": status,
                "role": role,
                "age": f"{age_days}d",
                "version": node.status.node_info.kubelet_version,
            }
        )

    return result


@api_router.get("/nodes/{node_name}")
def node_details(
    node_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "Cluster not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])

    v1 = k8s.CoreV1Api()
    node = v1.read_node(node_name)

    # Conditions
    conditions = [
        {"type": c.type, "status": c.status} for c in node.status.conditions or []
    ]

    # Capacity / Allocatable
    capacity = node.status.capacity or {}
    allocatable = node.status.allocatable or {}

    # Taints
    taints = [f"{t.key}={t.value}:{t.effect}" for t in (node.spec.taints or [])]

    return {
        "kind": "Node",
        "apiVersion": "v1",
        "metadata": {
            "name": node.metadata.name,
            "labels": node.metadata.labels or {},
            "annotations": node.metadata.annotations or {},
            "uid": node.metadata.uid,
            "creationTimestamp": node.metadata.creation_timestamp.isoformat()
            if node.metadata.creation_timestamp
            else None,
        },
        "spec": {"taints": taints, "unschedulable": node.spec.unschedulable or False},
        "status": {
            "conditions": conditions,
            "capacity": capacity,
            "allocatable": allocatable,
            "nodeInfo": {
                "kubeletVersion": node.status.node_info.kubelet_version
                if node.status.node_info
                else None,
                "kubeProxyVersion": node.status.node_info.kube_proxy_version
                if node.status.node_info
                else None,
                "osImage": node.status.node_info.os_image
                if node.status.node_info
                else None,
                "kernelVersion": node.status.node_info.kernel_version
                if node.status.node_info
                else None,
                "containerRuntimeVersion": node.status.node_info.container_runtime_version
                if node.status.node_info
                else None,
            },
        },
    }


@api_router.post("/nodes/{node_name}/cordon")
def cordon_node(
    node_name: str, request: Request, user=Depends(require_role(["admin"]))
):
    cluster_id = request.session.get("active_cluster")
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])

    v1 = k8s.CoreV1Api()
    body = {"spec": {"unschedulable": True}}
    v1.patch_node(node_name, body)

    audit_logs.insert_one(
        {
            "user": user["email"],
            "role": user["role"],
            "action": "cordon_node",
            "resource": f"node/{node_name}",
            "cluster_id": request.session.get("active_cluster"),
            "timestamp": datetime.now(timezone.utc),
        }
    )

    return {"status": "cordoned"}


@api_router.post("/nodes/{node_name}/uncordon")
def uncordon_node(
    node_name: str, request: Request, user=Depends(require_role(["admin"]))
):
    cluster_id = request.session.get("active_cluster")
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])

    v1 = k8s.CoreV1Api()
    body = {"spec": {"unschedulable": False}}
    v1.patch_node(node_name, body)

    audit_logs.insert_one(
        {
            "user": user["email"],
            "role": user["role"],
            "action": "uncordon_node",
            "resource": f"node/{node_name}",
            "cluster_id": request.session.get("active_cluster"),
            "timestamp": datetime.now(timezone.utc),
        }
    )

    return {"status": "uncordoned"}


@api_router.post("/nodes/{node_name}/drain")
def drain_node(node_name: str, request: Request, user=Depends(require_role(["admin"]))):
    cluster_id = request.session.get("active_cluster")
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])

    v1 = k8s.CoreV1Api()
    policy = k8s.PolicyV1Api()

    pods = v1.list_pod_for_all_namespaces(
        field_selector=f"spec.nodeName={node_name}"
    ).items

    for pod in pods:
        # Skip mirror pods / DaemonSets
        if pod.metadata.owner_references:
            if any(o.kind == "DaemonSet" for o in pod.metadata.owner_references):
                continue

        eviction = k8s.V1Eviction(
            metadata=k8s.V1ObjectMeta(
                name=pod.metadata.name, namespace=pod.metadata.namespace
            )
        )

        try:
            policy.create_namespaced_pod_eviction(
                name=pod.metadata.name, namespace=pod.metadata.namespace, body=eviction
            )
        except Exception:
            pass

    audit_logs.insert_one(
        {
            "user": user["email"],
            "role": user["role"],
            "action": "drain_node",
            "resource": f"node/{node_name}",
            "cluster_id": request.session.get("active_cluster"),
            "timestamp": datetime.now(timezone.utc),
        }
    )

    return {"status": "drain initiated"}
