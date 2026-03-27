from fastapi import APIRouter, Request, Depends, HTTPException
from bson import ObjectId

from kubernetes import client
from kubernetes.client.rest import ApiException

from app.auth.rbac import require_role
from app.db import clusters
from app.k8s.loader import load_k8s_client

router = APIRouter(prefix="/api/cluster")

@router.get("/overview")
def cluster_overview(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"]))
):
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "Cluster not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    # ✅ This sets global kube config
    load_k8s_client(cluster["kubeconfig_path"])

    try:
        v1 = client.CoreV1Api()
        version_api = client.VersionApi()

        # Kubernetes version
        version = version_api.get_code().git_version

        # Nodes
        nodes = v1.list_node().items
        ready_nodes = sum(
            1 for n in nodes
            for c in (n.status.conditions or [])
            if c.type == "Ready" and c.status == "True"
        )

        # Namespaces
        namespaces = v1.list_namespace().items

        # Pods
        pods = v1.list_pod_for_all_namespaces().items
        running_pods = sum(
            1 for p in pods if p.status.phase == "Running"
        )

        # Provider detection
        provider = "Vanilla Kubernetes"
        if nodes:
            labels = nodes[0].metadata.labels or {}
            if any("eks.amazonaws.com" in k for k in labels):
                provider = "Amazon EKS"
            elif any("cloud.google.com" in k for k in labels):
                provider = "Google GKE"
            elif any("kubernetes.azure.com" in k for k in labels):
                provider = "Azure AKS"
            elif any("node.openshift.io" in k for k in labels):
                provider = "OpenShift"

        return {
            "name": cluster["name"],
            "provider": provider,
            "version": version,
            "nodes": {
                "ready": ready_nodes,
                "total": len(nodes)
            },
            "namespaces": len(namespaces),
            "pods": {
                "running": running_pods,
                "total": len(pods)
            },
            "health": "Healthy" if ready_nodes == len(nodes) else "Degraded"
        }

    except ApiException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Kubernetes API error: {e.reason}"
        )