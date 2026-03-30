"""
Cost Analysis Routes

Provides REST API endpoints for cluster cost estimation:
- Per-namespace cost breakdown
- Per-workload cost breakdown
- Right-sizing recommendations (requests vs usage)
- Monthly cost projections
- Configurable pricing rates (CPU $/core/hr, Memory $/GB/hr, Storage $/GB/month)

Costs are estimated based on resource requests (not actual usage).
Right-sizing compares requests against actual CPU/memory usage from metrics.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.db import clusters
from app.k8s.loader import load_k8s_client
from bson import ObjectId
from datetime import datetime, timezone
import logging

router = APIRouter(prefix="/api/cost")
logger = logging.getLogger(__name__)


def get_k8s_context(request: Request):
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
    """Get k8s context with api_client, host, and token for metrics."""
    from app.k8s.loader import get_k8s_config

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
        logger.error(f"Failed to get k8s context with config: {e}")
        raise HTTPException(500, f"Failed to load cluster: {str(e)}")


def parse_cpu(cpu_str):
    """Parse CPU string (e.g., '500m', '2', '0.5') to cores (float)."""
    if not cpu_str:
        return 0.0
    cpu_str = str(cpu_str).strip()
    if cpu_str.endswith("m"):
        return float(cpu_str[:-1]) / 1000.0
    return float(cpu_str)


def parse_memory(mem_str):
    """Parse memory string (e.g., '256Mi', '1Gi', '512000000') to bytes."""
    if not mem_str:
        return 0
    mem_str = str(mem_str).strip()
    multipliers = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
    }
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if mem_str.endswith(suffix):
            return int(float(mem_str[: -len(suffix)]) * mult)
    try:
        return int(mem_str)
    except ValueError:
        return 0


def bytes_to_gb(b):
    return round(b / (1024**3), 4)


DEFAULT_PRICING = {
    "cpu_per_core_hour": 0.0425,  # ~$31/core/month (AWS m5 pricing)
    "memory_per_gb_hour": 0.005,  # ~$3.65/GB/month
    "storage_per_gb_month": 0.10,  # AWS gp3 pricing
}


@router.get("/analyze")
def analyze_costs(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Analyze cluster costs based on resource requests.

    Returns namespace breakdown, workload breakdown, and total costs.
    """
    try:
        k8s, namespace = get_k8s_context(request)
        apps_v1 = k8s.AppsV1Api()
        v1 = k8s.CoreV1Api()

        pricing = DEFAULT_PRICING

        # Get pods
        if namespace == "_all":
            pods = v1.list_pod_for_all_namespaces().items
        else:
            pods = v1.list_namespaced_pod(namespace).items

        # Get node count for context
        nodes = v1.list_node().items
        node_count = len(nodes)

        # Calculate per-pod resource requests
        namespace_costs = {}
        workload_costs = []

        for pod in pods:
            ns = pod.metadata.namespace or "default"
            pod_name = pod.metadata.name
            owner_kind = ""
            owner_name = pod_name

            # Find owning controller
            if pod.metadata.owner_references:
                owner = pod.metadata.owner_references[0]
                owner_kind = owner.kind or ""
                owner_name = owner.name or pod_name

            total_cpu_request = 0.0
            total_mem_request = 0

            for container in pod.spec.containers or []:
                if container.resources and container.resources.requests:
                    cpu_str = container.resources.requests.get("cpu", "0")
                    mem_str = container.resources.requests.get("memory", "0")
                    total_cpu_request += parse_cpu(cpu_str)
                    total_mem_request += parse_memory(mem_str)

            # Hourly cost
            cpu_cost_hour = total_cpu_request * pricing["cpu_per_core_hour"]
            mem_cost_hour = (
                bytes_to_gb(total_mem_request) * pricing["memory_per_gb_hour"]
            )
            pod_cost_hour = cpu_cost_hour + mem_cost_hour

            # Monthly cost (730 hours)
            pod_cost_month = pod_cost_hour * 730

            # Track by namespace
            if ns not in namespace_costs:
                namespace_costs[ns] = {
                    "namespace": ns,
                    "pod_count": 0,
                    "total_cpu_cores": 0,
                    "total_memory_gb": 0,
                    "cpu_cost_month": 0,
                    "memory_cost_month": 0,
                    "total_cost_month": 0,
                }

            ns_data = namespace_costs[ns]
            ns_data["pod_count"] += 1
            ns_data["total_cpu_cores"] += total_cpu_request
            ns_data["total_memory_gb"] += bytes_to_gb(total_mem_request)
            ns_data["cpu_cost_month"] += cpu_cost_hour * 730
            ns_data["memory_cost_month"] += mem_cost_hour * 730
            ns_data["total_cost_month"] += pod_cost_month

            # Track by workload
            workload_costs.append(
                {
                    "name": owner_name,
                    "kind": owner_kind,
                    "namespace": ns,
                    "pod_name": pod_name,
                    "cpu_cores": round(total_cpu_request, 4),
                    "memory_gb": bytes_to_gb(total_mem_request),
                    "cpu_cost_month": round(cpu_cost_hour * 730, 2),
                    "memory_cost_month": round(mem_cost_hour * 730, 2),
                    "total_cost_month": round(pod_cost_month, 2),
                }
            )

        # Round namespace costs
        for ns_data in namespace_costs.values():
            ns_data["total_cpu_cores"] = round(ns_data["total_cpu_cores"], 4)
            ns_data["total_memory_gb"] = round(ns_data["total_memory_gb"], 4)
            ns_data["cpu_cost_month"] = round(ns_data["cpu_cost_month"], 2)
            ns_data["memory_cost_month"] = round(ns_data["memory_cost_month"], 2)
            ns_data["total_cost_month"] = round(ns_data["total_cost_month"], 2)

        # Aggregate workload costs by controller
        controller_costs = {}
        for wc in workload_costs:
            key = f"{wc['namespace']}/{wc['kind']}/{wc['name']}"
            if key not in controller_costs:
                controller_costs[key] = {
                    "name": wc["name"],
                    "kind": wc["kind"],
                    "namespace": wc["namespace"],
                    "pod_count": 0,
                    "cpu_cores": 0,
                    "memory_gb": 0,
                    "cpu_cost_month": 0,
                    "memory_cost_month": 0,
                    "total_cost_month": 0,
                }
            cc = controller_costs[key]
            cc["pod_count"] += 1
            cc["cpu_cores"] += wc["cpu_cores"]
            cc["memory_gb"] += wc["memory_gb"]
            cc["cpu_cost_month"] += wc["cpu_cost_month"]
            cc["memory_cost_month"] += wc["memory_cost_month"]
            cc["total_cost_month"] += wc["total_cost_month"]

        # Round controller costs
        for cc in controller_costs.values():
            cc["cpu_cores"] = round(cc["cpu_cores"], 4)
            cc["memory_gb"] = round(cc["memory_gb"], 4)
            cc["cpu_cost_month"] = round(cc["cpu_cost_month"], 2)
            cc["memory_cost_month"] = round(cc["memory_cost_month"], 2)
            cc["total_cost_month"] = round(cc["total_cost_month"], 2)

        # Sort controllers by cost descending
        sorted_controllers = sorted(
            controller_costs.values(), key=lambda x: x["total_cost_month"], reverse=True
        )

        # Total
        total_cpu_month = sum(ns["cpu_cost_month"] for ns in namespace_costs.values())
        total_mem_month = sum(
            ns["memory_cost_month"] for ns in namespace_costs.values()
        )

        # Get PVC storage costs
        try:
            if namespace == "_all":
                pvcs = v1.list_persistent_volume_claim_for_all_namespaces().items
            else:
                pvcs = v1.list_namespaced_persistent_volume_claim(namespace).items

            storage_cost_total = 0
            for pvc in pvcs:
                if pvc.spec.resources and pvc.spec.resources.requests:
                    storage_str = pvc.spec.resources.requests.get("storage", "0")
                    storage_bytes = parse_memory(storage_str)
                    storage_gb = bytes_to_gb(storage_bytes)
                    storage_cost_total += storage_gb * pricing["storage_per_gb_month"]
        except Exception:
            storage_cost_total = 0

        return {
            "total_monthly_cost": round(
                total_cpu_month + total_mem_month + storage_cost_total, 2
            ),
            "cpu_cost_month": round(total_cpu_month, 2),
            "memory_cost_month": round(total_mem_month, 2),
            "storage_cost_month": round(storage_cost_total, 2),
            "node_count": node_count,
            "pod_count": len(pods),
            "namespace_breakdown": list(namespace_costs.values()),
            "workload_breakdown": sorted_controllers[:50],
            "pricing": pricing,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing costs: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to analyze costs: {str(e)}")


@router.get("/rightsize")
def rightsizing_recommendations(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Get right-sizing recommendations by comparing resource requests vs actual usage.

    Returns workloads where requests significantly exceed usage (over-provisioned)
    or where usage exceeds requests (under-provisioned).
    """
    try:
        k8s, namespace, api_client, host, token = get_k8s_context_with_config(request)
        apps_v1 = k8s.AppsV1Api()
        v1 = k8s.CoreV1Api()

        # Get pods with requests
        if namespace == "_all":
            pods = v1.list_pod_for_all_namespaces().items
        else:
            pods = v1.list_namespaced_pod(namespace).items

        # Try to get actual usage from metrics API
        pod_usage = {}
        try:
            from app.k8s import metrics as metrics_mod

            cache = metrics_mod.get_cache()
            cache.clear()
            all_pod_metrics = metrics_mod.parse_pod_metrics(
                api_client, namespace, host, token
            )

            for pm in all_pod_metrics:
                pod_usage[pm.get("name", "")] = {
                    "cpu": pm.get("cpu_cores", 0) or 0,
                    "memory": pm.get("memory_bytes", 0) or 0,
                }
            logger.info(f"Got {len(pod_usage)} pod metrics for right-sizing")
        except Exception as e:
            logger.error(f"Could not get metrics for right-sizing: {e}", exc_info=True)

        recommendations = []

        for pod in pods:
            ns = pod.metadata.namespace or "default"
            pod_name = pod.metadata.name
            owner_kind = ""
            owner_name = pod_name

            if pod.metadata.owner_references:
                owner = pod.metadata.owner_references[0]
                owner_kind = owner.kind or ""
                owner_name = owner.name or pod_name

            total_cpu_request = 0.0
            total_mem_request = 0

            for container in pod.spec.containers or []:
                if container.resources and container.resources.requests:
                    cpu_str = container.resources.requests.get("cpu", "0")
                    mem_str = container.resources.requests.get("memory", "0")
                    total_cpu_request += parse_cpu(cpu_str)
                    total_mem_request += parse_memory(mem_str)

            if total_cpu_request == 0 and total_mem_request == 0:
                continue

            usage = pod_usage.get(pod_name, {"cpu": 0, "memory": 0})
            cpu_usage = usage["cpu"]
            mem_usage = usage["memory"]

            # Calculate utilization percentage
            cpu_util = (
                (cpu_usage / total_cpu_request * 100) if total_cpu_request > 0 else 0
            )
            mem_util = (
                (mem_usage / total_mem_request * 100) if total_mem_request > 0 else 0
            )

            # Determine status
            status = "ok"
            if cpu_util < 20 and mem_util < 20:
                status = "over-provisioned"
            elif cpu_util > 90 or mem_util > 90:
                status = "under-provisioned"

            if status != "ok":
                # Calculate recommended requests (add 20% buffer to actual usage)
                rec_cpu = max(cpu_usage * 1.2, 0.05)
                rec_mem = max(mem_usage * 1.2, 128 * 1024 * 1024)  # min 128Mi

                current_cost = (
                    total_cpu_request * DEFAULT_PRICING["cpu_per_core_hour"]
                    + bytes_to_gb(total_mem_request)
                    * DEFAULT_PRICING["memory_per_gb_hour"]
                ) * 730

                recommended_cost = (
                    rec_cpu * DEFAULT_PRICING["cpu_per_core_hour"]
                    + bytes_to_gb(rec_mem) * DEFAULT_PRICING["memory_per_gb_hour"]
                ) * 730

                savings = round(current_cost - recommended_cost, 2)

                recommendations.append(
                    {
                        "pod_name": pod_name,
                        "controller_name": owner_name,
                        "controller_kind": owner_kind,
                        "namespace": ns,
                        "status": status,
                        "cpu_requested": round(total_cpu_request, 4),
                        "cpu_used": round(cpu_usage, 4),
                        "cpu_utilization": round(cpu_util, 1),
                        "cpu_recommended": round(rec_cpu, 4),
                        "memory_requested_gb": bytes_to_gb(total_mem_request),
                        "memory_used_gb": bytes_to_gb(mem_usage),
                        "memory_utilization": round(mem_util, 1),
                        "memory_recommended_gb": bytes_to_gb(rec_mem),
                        "current_cost_month": round(current_cost, 2),
                        "recommended_cost_month": round(recommended_cost, 2),
                        "savings_month": max(savings, 0),
                    }
                )

        # Sort by savings descending
        recommendations.sort(key=lambda x: x["savings_month"], reverse=True)

        total_savings = sum(r["savings_month"] for r in recommendations)

        return {
            "recommendations": recommendations[:50],
            "total_recommendations": len(recommendations),
            "potential_savings_month": round(total_savings, 2),
            "has_metrics": len(pod_usage) > 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting right-sizing recommendations: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get recommendations: {str(e)}")
