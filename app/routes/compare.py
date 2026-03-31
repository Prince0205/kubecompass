"""
Multi-Cluster Comparison Routes

Provides REST API endpoints for comparing Kubernetes resources across clusters:
- List available clusters for comparison
- Fetch resources from multiple clusters
- Compute diff between resources across clusters
- Sync resources from one cluster to another
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
from kubernetes import config, client as k8s_client
import yaml
import logging
import difflib

router = APIRouter(prefix="/api/compare")
logger = logging.getLogger(__name__)

SUPPORTED_RESOURCE_TYPES = {
    "deployments": {
        "api": "apps",
        "method": "list_namespaced_deployment",
        "all_method": "list_deployment_for_all_namespaces",
        "read_method": "read_namespaced_deployment",
        "kind": "Deployment",
    },
    "services": {
        "api": "core",
        "method": "list_namespaced_service",
        "all_method": "list_service_for_all_namespaces",
        "read_method": "read_namespaced_service",
        "kind": "Service",
    },
    "configmaps": {
        "api": "core",
        "method": "list_namespaced_config_map",
        "all_method": "list_config_map_for_all_namespaces",
        "read_method": "read_namespaced_config_map",
        "kind": "ConfigMap",
    },
    "secrets": {
        "api": "core",
        "method": "list_namespaced_secret",
        "all_method": "list_secret_for_all_namespaces",
        "read_method": "read_namespaced_secret",
        "kind": "Secret",
    },
    "statefulsets": {
        "api": "apps",
        "method": "list_namespaced_stateful_set",
        "all_method": "list_stateful_set_for_all_namespaces",
        "read_method": "read_namespaced_stateful_set",
        "kind": "StatefulSet",
    },
    "daemonsets": {
        "api": "apps",
        "method": "list_namespaced_daemon_set",
        "all_method": "list_daemon_set_for_all_namespaces",
        "read_method": "read_namespaced_daemon_set",
        "kind": "DaemonSet",
    },
    "jobs": {
        "api": "batch",
        "method": "list_namespaced_job",
        "all_method": "list_job_for_all_namespaces",
        "read_method": "read_namespaced_job",
        "kind": "Job",
    },
    "cronjobs": {
        "api": "batch",
        "method": "list_namespaced_cron_job",
        "all_method": "list_cron_job_for_all_namespaces",
        "read_method": "read_namespaced_cron_job",
        "kind": "CronJob",
    },
    "ingresses": {
        "api": "networking",
        "method": "list_namespaced_ingress",
        "all_method": "list_ingress_for_all_namespaces",
        "read_method": "read_namespaced_ingress",
        "kind": "Ingress",
    },
    "persistentvolumeclaims": {
        "api": "core",
        "method": "list_namespaced_persistent_volume_claim",
        "all_method": "list_persistent_volume_claim_for_all_namespaces",
        "read_method": "read_namespaced_persistent_volume_claim",
        "kind": "PersistentVolumeClaim",
    },
}


def _get_api_client(cluster_id: str):
    """Load an isolated k8s client for a given cluster ID.

    Uses a separate ApiClient/configuration per cluster to avoid global
    config conflicts when querying two clusters simultaneously.
    """
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(404, f"Cluster {cluster_id} not found")

    kubeconfig_path = cluster.get("kubeconfig_path")
    try:
        cfg = k8s_client.Configuration()
        if kubeconfig_path:
            config.load_kube_config(
                config_file=kubeconfig_path,
                client_configuration=cfg,
            )
        else:
            config.load_incluster_config(client_configuration=cfg)
    except Exception as e:
        logger.error(f"Failed to load kubeconfig for cluster {cluster['name']}: {e}")
        raise HTTPException(
            500, f"Could not load kubeconfig for cluster {cluster['name']}: {str(e)}"
        )

    api_client = k8s_client.ApiClient(configuration=cfg)
    return api_client, cluster["name"]


def _get_api_for_type(api_client, resource_type: str):
    """Get the appropriate API instance for a resource type.

    api_client is a kubernetes.client.ApiClient instance with the correct
    cluster configuration. Each API is created with this specific client
    to avoid global config conflicts.
    """
    info = SUPPORTED_RESOURCE_TYPES[resource_type]
    api_name = info["api"]
    if api_name == "core":
        return k8s_client.CoreV1Api(api_client)
    elif api_name == "apps":
        return k8s_client.AppsV1Api(api_client)
    elif api_name == "batch":
        return k8s_client.BatchV1Api(api_client)
    elif api_name == "networking":
        return k8s_client.NetworkingV1Api(api_client)
    raise HTTPException(400, f"Unknown API: {api_name}")


def _serialize_resource(resource):
    """Serialize a Kubernetes resource to a clean dict."""
    if resource is None:
        return None
    try:
        d = resource.to_dict()
        # Remove server-managed fields for cleaner comparison
        meta = d.get("metadata", {})
        for key in [
            "resourceVersion",
            "uid",
            "creationTimestamp",
            "generation",
            "managedFields",
            "selfLink",
        ]:
            meta.pop(key, None)
            meta.pop("resource_version", None)
            meta.pop("uid", None)
            meta.pop("creation_timestamp", None)
            meta.pop("generation", None)
            meta.pop("managed_fields", None)
            meta.pop("self_link", None)
        # Remove status (server-managed)
        d.pop("status", None)
        return d
    except Exception:
        return {"name": str(resource)}


def _list_resources(api, resource_type: str, namespace: str):
    """List resources from a cluster."""
    info = SUPPORTED_RESOURCE_TYPES[resource_type]
    try:
        if namespace and namespace not in ("_all_", "_all"):
            method = getattr(api, info["method"])
            items = method(namespace).items
        else:
            method = getattr(api, info["all_method"])
            items = method().items
        result = {}
        for item in items:
            name = item.metadata.name
            ns = item.metadata.namespace or ""
            key = f"{ns}/{name}" if ns else name
            result[key] = _serialize_resource(item)
        return result
    except Exception as e:
        logger.error(f"Error listing {resource_type}: {e}")
        return {}


def _compute_diff(yaml_a: str, yaml_b: str) -> list:
    """Compute unified diff between two YAML strings."""
    lines_a = yaml_a.splitlines(keepends=True)
    lines_b = yaml_b.splitlines(keepends=True)
    diff = list(difflib.unified_diff(lines_a, lines_b, lineterm=""))
    return diff


@router.get("/clusters")
def list_clusters_for_compare(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """List all available clusters for comparison."""
    cluster_list = list(clusters.find({}, {"name": 1, "provider": 1}))
    return [
        {"id": str(c["_id"]), "name": c["name"], "provider": c.get("provider", "")}
        for c in cluster_list
    ]


@router.get("/resource-types")
def list_resource_types(
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """List supported resource types for comparison."""
    return [
        {"key": key, "kind": info["kind"]}
        for key, info in SUPPORTED_RESOURCE_TYPES.items()
    ]


@router.get("/resources")
def compare_resources(
    request: Request,
    cluster_a: str = Query(...),
    cluster_b: str = Query(...),
    resource_type: str = Query(...),
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Compare resources across two clusters."""
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        raise HTTPException(400, f"Unsupported resource type: {resource_type}")

    if cluster_a == cluster_b:
        raise HTTPException(400, "Select two different clusters to compare")

    try:
        k8s_a, name_a = _get_api_client(cluster_a)
        k8s_b, name_b = _get_api_client(cluster_b)

        api_a = _get_api_for_type(k8s_a, resource_type)
        api_b = _get_api_for_type(k8s_b, resource_type)

        ns = namespace or "default"
        resources_a = _list_resources(api_a, resource_type, ns)
        resources_b = _list_resources(api_b, resource_type, ns)

        all_keys = sorted(set(list(resources_a.keys()) + list(resources_b.keys())))

        comparisons = []
        for key in all_keys:
            res_a = resources_a.get(key)
            res_b = resources_b.get(key)

            in_a = res_a is not None
            in_b = res_b is not None

            yaml_a = yaml.dump(res_a, default_flow_style=False) if res_a else ""
            yaml_b = yaml.dump(res_b, default_flow_style=False) if res_b else ""

            if in_a and in_b:
                diff = _compute_diff(yaml_a, yaml_b)
                status = "identical" if not diff else "drifted"
            elif in_a and not in_b:
                diff = _compute_diff(yaml_a, "")
                status = "only_in_a"
            else:
                diff = _compute_diff("", yaml_b)
                status = "only_in_b"

            comparisons.append(
                {
                    "resource_key": key,
                    "status": status,
                    "in_cluster_a": in_a,
                    "in_cluster_b": in_b,
                    "yaml_a": yaml_a,
                    "yaml_b": yaml_b,
                    "diff": diff,
                }
            )

        summary = {
            "total": len(comparisons),
            "identical": sum(1 for c in comparisons if c["status"] == "identical"),
            "drifted": sum(1 for c in comparisons if c["status"] == "drifted"),
            "only_in_a": sum(1 for c in comparisons if c["status"] == "only_in_a"),
            "only_in_b": sum(1 for c in comparisons if c["status"] == "only_in_b"),
        }

        return {
            "cluster_a": {"id": cluster_a, "name": name_a},
            "cluster_b": {"id": cluster_b, "name": name_b},
            "resource_type": resource_type,
            "namespace": ns,
            "summary": summary,
            "comparisons": comparisons,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing resources: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to compare resources: {str(e)}")


@router.get("/namespaces")
def list_namespaces_for_cluster(
    cluster_id: str = Query(...),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """List namespaces for a specific cluster."""
    try:
        k8s, _ = _get_api_client(cluster_id)
        v1 = k8s.CoreV1Api()
        namespaces = [ns.metadata.name for ns in v1.list_namespace().items]
        return sorted(namespaces)
    except Exception as e:
        logger.error(f"Error listing namespaces: {e}")
        raise HTTPException(500, f"Failed to list namespaces: {str(e)}")
