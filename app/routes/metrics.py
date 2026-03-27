"""
Metrics API Routes

Provides REST API endpoints for retrieving Kubernetes metrics (CPU, Memory, Disk, Network).
Used by dashboard to display real-time cluster and resource metrics.

Endpoints:
  GET /api/metrics/cluster        - Cluster-wide metrics
  GET /api/metrics/nodes          - Node metrics
  GET /api/metrics/namespace/{ns} - Namespace resource usage
  GET /api/metrics/pod/{ns}/{pod} - Pod-specific metrics
  GET /api/metrics/pvc/{ns}       - PVC usage metrics
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client, get_k8s_config
from app.db import clusters
from bson import ObjectId
from app.k8s import metrics
import logging

router = APIRouter(prefix="/api/metrics")
logger = logging.getLogger(__name__)


def get_k8s_context(request: Request):
    """Extract cluster and namespace from session.

    Returns: (k8s_client_module, namespace) for backward compatibility
    For metrics, use get_k8s_context_with_config instead
    """
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace", "default")

    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])
        return k8s, namespace
    except Exception as e:
        logger.error(f"Failed to get k8s context: {e}")
        raise HTTPException(500, f"Failed to load cluster: {str(e)}")


def get_k8s_context_with_config(request: Request):
    """Extract cluster and namespace from session with API config for metrics."""
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace", "default")

    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])
        config_data = get_k8s_config(cluster["kubeconfig_path"])
        return (
            k8s,
            namespace,
            config_data["api_client"],
            config_data.get("host"),
            config_data.get("token"),
        )
    except Exception as e:
        logger.error(f"Failed to get k8s context: {e}")
        raise HTTPException(500, f"Failed to load cluster: {str(e)}")


# =============================================================================
# CLUSTER-WIDE METRICS
# =============================================================================


@router.get("/cluster")
def get_cluster_metrics(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """
    Get cluster-wide metrics summary.

    Returns:
      {
        "total_nodes": int,
        "total_pods": int,
        "total_cpu_cores": float,
        "total_memory_bytes": int,
        "average_pod_cpu": float,
        "average_pod_memory": int,
        "node_metrics": [...],
        "namespaces": [...]
      }
    """
    try:
        k8s_client_module, namespace, api_client, host, token = (
            get_k8s_context_with_config(request)
        )
        logger.info("Getting cluster metrics")
        logger.info(f"API Host: {host}")
        logger.info(f"Token available: {token is not None}")

        # Get node metrics directly with api_client and host
        node_metrics = []
        try:
            node_metrics = metrics.parse_node_metrics(api_client, host, token)
        except Exception as e:
            logger.error(f"Error parsing node metrics: {e}")

        logger.info(f"Got {len(node_metrics)} node metrics")

        if not node_metrics:
            # If no metrics, return basic info with error details
            v1 = k8s_client_module.CoreV1Api()
            nodes = v1.list_node().items

            # Try to get pod count anyway
            pod_count = 0
            try:
                all_pods = v1.list_pod_for_all_namespaces().items
                pod_count = len(all_pods)
            except Exception as e:
                logger.warning(f"Failed to get pod count: {e}")

            return {
                "total_nodes": len(nodes),
                "total_pods": pod_count,
                "total_cpu_cores": 0,
                "total_memory_bytes": 0,
                "average_pod_cpu": 0,
                "average_pod_memory": 0,
                "node_metrics": [],
                "namespaces": [],
                "warning": "Metrics Server API not accessible. The metrics.k8s.io API is not returning data. Check RBAC permissions and ensure Metrics Server is properly configured.",
                "metrics_installed": True,
                "kubectl_top_works": True,
            }

        # Aggregate node metrics
        node_summary = metrics.aggregate_node_metrics(node_metrics)

        # Get namespace summary
        v1 = k8s_client_module.CoreV1Api()
        namespaces = v1.list_namespace().items
        namespace_count = len(namespaces)

        # Get pod count
        pod_count = 0
        try:
            all_pods = v1.list_pod_for_all_namespaces().items
            pod_count = len(all_pods)
            logger.info(f"Found {pod_count} pods in cluster")
        except Exception as e:
            logger.error(f"Error getting pod count: {e}")

        return {
            "total_nodes": node_summary.get("node_count", 0),
            "total_pods": pod_count,
            "total_cpu_cores": node_summary.get("total_cpu", 0),
            "total_memory_bytes": node_summary.get("total_memory", 0),
            "average_node_cpu": node_summary.get("average_cpu", 0),
            "average_node_memory": node_summary.get("average_memory", 0),
            "namespace_count": namespace_count,
            "node_metrics": node_metrics,
            "timestamp": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cluster metrics: {e}")
        raise HTTPException(500, f"Failed to get cluster metrics: {str(e)}")


# =============================================================================
# NODE METRICS
# =============================================================================


@router.get("/nodes")
def get_nodes_metrics(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """
    Get metrics for all nodes in cluster.

    Returns:
      [
        {
          "name": "node-1",
          "cpu": "500m",
          "memory": "2Gi",
          "cpu_cores": 0.5,
          "memory_bytes": 2147483648,
          "status": "Ready"
        },
        ...
      ]
    """
    try:
        k8s_client_module, namespace, api_client, host, token = (
            get_k8s_context_with_config(request)
        )

        # Clear cache and get fresh metrics
        cache = metrics.get_cache()
        cache.clear()

        node_metrics = metrics.parse_node_metrics(api_client, host, token)

        # Add node status
        v1 = k8s_client_module.CoreV1Api()
        nodes = v1.list_node().items
        node_statuses = {n.metadata.name: "Ready" for n in nodes}

        for metric in node_metrics:
            metric["status"] = node_statuses.get(metric["name"], "Unknown")

        return node_metrics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node metrics: {e}")
        raise HTTPException(500, f"Failed to get node metrics: {str(e)}")


@router.get("/nodes/{node_name}")
def get_node_metrics(
    node_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Get metrics for specific node.

    Returns:
      {
        "name": "node-1",
        "cpu": "500m",
        "memory": "2Gi",
        "cpu_cores": 0.5,
        "memory_bytes": 2147483648,
        "status": "Ready",
        "allocatable_cpu": "2",
        "allocatable_memory": "8Gi"
      }
    """
    try:
        k8s_client_module, namespace, api_client, host, token = (
            get_k8s_context_with_config(request)
        )
        cache = metrics.get_cache()

        node_metrics = metrics.parse_node_metrics(api_client, host, token)

        # Find node
        node_metric = next((n for n in node_metrics if n["name"] == node_name), None)
        if not node_metric:
            raise HTTPException(404, f"Node {node_name} not found")

        # Get node details
        v1 = k8s_client_module.CoreV1Api()
        node = v1.read_node(node_name)

        node_metric["status"] = "Ready"  # simplified
        if node.status.conditions:
            for cond in node.status.conditions:
                if cond.type == "Ready" and cond.status != "True":
                    node_metric["status"] = "NotReady"

        if node.status.allocatable:
            node_metric["allocatable_cpu"] = node.status.allocatable.get("cpu", "0")
            node_metric["allocatable_memory"] = node.status.allocatable.get(
                "memory", "0Mi"
            )

        return node_metric

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node metrics: {e}")
        raise HTTPException(500, f"Failed to get node {node_name} metrics: {str(e)}")


# =============================================================================
# NAMESPACE METRICS
# =============================================================================


@router.get("/namespace/{namespace}")
def get_namespace_metrics(
    namespace: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Get resource usage metrics for a namespace.

    Returns:
      {
        "name": "default",
        "total_pods": 5,
        "total_cpu_cores": 0.5,
        "total_memory_bytes": 1073741824,
        "pod_metrics": [...]
      }
    """
    try:
        k8s_client_module, namespace, api_client, host, token = (
            get_k8s_context_with_config(request)
        )
        cache = metrics.get_cache()

        # Get pod metrics for namespace using api_client
        pod_metrics = metrics.get_cached_pod_metrics(api_client, namespace, cache)

        # Aggregate
        aggregated = metrics.aggregate_pod_metrics_by_namespace(pod_metrics)

        ns_data = aggregated.get(namespace, {"cpu": 0, "memory": 0, "pod_count": 0})

        return {
            "name": namespace,
            "cpu_used": ns_data.get("cpu", 0),
            "memory_used": ns_data.get("memory", 0),
            "pod_count": ns_data.get("pod_count", 0),
            "total_pods": ns_data.get("pod_count", 0),
            "total_cpu_cores": ns_data.get("cpu", 0),
            "total_memory_bytes": ns_data.get("memory", 0),
            "pod_metrics": pod_metrics,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting namespace metrics: {e}")
        raise HTTPException(500, f"Failed to get namespace metrics: {str(e)}")


# =============================================================================
# POD METRICS
# =============================================================================


@router.get("/pod/{namespace}/{pod_name}")
def get_pod_metrics(
    namespace: str,
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Get metrics for specific pod.

    Returns:
      {
        "name": "pod-abc123",
        "namespace": "default",
        "cpu": "100m",
        "memory": "256Mi",
        "cpu_cores": 0.1,
        "memory_bytes": 268435456,
        "containers": [...]
      }
    """
    try:
        k8s, _ = get_k8s_context(request)
        cache = metrics.get_cache()

        # Get all pod metrics for namespace
        pod_metrics = metrics.get_cached_pod_metrics(k8s, namespace, cache)

        # Find specific pod
        pod_metric = next((p for p in pod_metrics if p["name"] == pod_name), None)
        if not pod_metric:
            raise HTTPException(
                404, f"Pod {pod_name} not found in namespace {namespace}"
            )

        return pod_metric

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pod metrics: {e}")
        raise HTTPException(500, f"Failed to get pod metrics: {str(e)}")


# =============================================================================
# PVC METRICS (Storage Usage)
# =============================================================================


@router.get("/pvc/{namespace}")
def get_pvc_metrics(
    namespace: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Get PVC usage metrics for namespace.

    Returns:
      [
        {
          "name": "data-pvc",
          "namespace": "default",
          "status": "Bound",
          "capacity": "10Gi",
          "used": "5Gi",
          "available": "5Gi",
          "usage_percent": 50
        },
        ...
      ]
    """
    try:
        k8s_client_module, namespace, api_client, host, token = (
            get_k8s_context_with_config(request)
        )

        v1 = k8s_client_module.CoreV1Api()
        pvcs = v1.list_namespaced_persistent_volume_claim(namespace).items

        result = []
        for pvc in pvcs:
            name = pvc.metadata.name
            status = pvc.status.phase if pvc.status else "Unknown"

            # Get capacity
            capacity_str = "0Gi"
            if pvc.spec.resources and pvc.spec.resources.requests:
                capacity_str = pvc.spec.resources.requests.get("storage", "0Gi")

            # PVC usage requires actual pod exec or kubelet metrics
            # For now, return capacity as placeholder
            capacity_bytes = metrics.convert_memory_to_bytes(capacity_str)

            result.append(
                {
                    "name": name,
                    "namespace": namespace,
                    "status": status,
                    "capacity": capacity_str,
                    "capacity_bytes": capacity_bytes,
                    "used": "0Gi",  # Would need pod metrics or kubelet
                    "available": capacity_str,
                    "usage_percent": 0,
                    "storage_class": pvc.spec.storage_class_name,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PVC metrics: {e}")
        raise HTTPException(500, f"Failed to get PVC metrics: {str(e)}")


# =============================================================================
# HEALTH CHECK
# =============================================================================


@router.get("/health")
def metrics_health(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """
    Check if metrics collection is available.

    Returns:
      {
        "status": "healthy" | "degraded",
        "metrics_server_available": bool,
        "cache_enabled": bool,
        "cache_ttl_seconds": int
      }
    """
    try:
        k8s, _ = get_k8s_context(request)

        # Try to get any metrics to verify Metrics Server
        node_metrics = metrics.parse_node_metrics(k8s)
        metrics_available = len(node_metrics) > 0

        cache = metrics.get_cache()

        return {
            "status": "healthy" if metrics_available else "degraded",
            "metrics_server_available": metrics_available,
            "cache_enabled": cache is not None,
            "cache_ttl_seconds": cache.ttl_seconds if cache else 0,
        }

    except Exception as e:
        logger.error(f"Error checking metrics health: {e}")
        return {
            "status": "degraded",
            "metrics_server_available": False,
            "cache_enabled": True,
            "error": str(e),
        }


# =============================================================================
# End of Routes
# =============================================================================
