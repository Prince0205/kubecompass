"""
Configuration Resource Management Endpoints
Handles: ConfigMaps, Secrets, HPAs, ResourceQuotas, LimitRanges
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from kubernetes.client.rest import ApiException
from app.auth.rbac import require_role
from app.auth.session import get_current_user
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging

router = APIRouter(prefix="/api/resources/config", tags=["config"])
logger = logging.getLogger(__name__)


def get_k8s_context(request: Request):
    """Extract cluster and namespace from session."""
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


# =============================================================================
# CONFIGMAP ENDPOINTS
# =============================================================================


@router.get("/configmaps")
async def list_configmaps(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all ConfigMaps in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        configmaps = v1.list_namespaced_config_map(namespace)

        result = []
        for cm in configmaps.items:
            result.append(
                {
                    "name": cm.metadata.name,
                    "namespace": cm.metadata.namespace,
                    "data_count": len(cm.data) if cm.data else 0,
                    "created": cm.metadata.creation_timestamp,
                }
            )
        return {"configmaps": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing ConfigMaps: {str(e)}"
        )


@router.get("/configmaps/{name}")
async def get_configmap_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get ConfigMap detail including data"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        cm = v1.read_namespaced_config_map(name, namespace)

        return {
            "kind": "ConfigMap",
            "apiVersion": "v1",
            "metadata": {
                "name": cm.metadata.name,
                "namespace": cm.metadata.namespace,
                "labels": cm.metadata.labels or {},
                "annotations": cm.metadata.annotations or {},
                "uid": cm.metadata.uid,
                "creationTimestamp": cm.metadata.creation_timestamp.isoformat()
                if cm.metadata.creation_timestamp
                else None,
            },
            "data": cm.data or {},
            "binaryData": cm.binary_data or {},
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"ConfigMap '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting ConfigMap: {str(e)}"
        )


@router.put("/configmaps/{name}")
async def edit_configmap(
    name: str,
    data: dict,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Edit ConfigMap data"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        cm = v1.read_namespaced_config_map(name, namespace)

        # Update data
        cm.data = data.get("data", {})

        updated = v1.patch_namespaced_config_map(name, namespace, cm)

        return {
            "status": "updated",
            "name": updated.metadata.name,
            "data_count": len(updated.data) if updated.data else 0,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"ConfigMap '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating ConfigMap: {str(e)}"
        )


@router.delete("/configmaps/{name}")
async def delete_configmap(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a ConfigMap"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        v1.delete_namespaced_config_map(name, namespace)

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"ConfigMap '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting ConfigMap: {str(e)}"
        )


# =============================================================================
# SECRET ENDPOINTS
# =============================================================================


@router.get("/secrets")
async def list_secrets(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all Secrets in the current namespace (limited info for security)"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        secrets = v1.list_namespaced_secret(namespace)

        result = []
        for secret in secrets.items:
            result.append(
                {
                    "name": secret.metadata.name,
                    "namespace": secret.metadata.namespace,
                    "type": secret.type,
                    "keys_count": len(secret.data) if secret.data else 0,
                    "created": secret.metadata.creation_timestamp,
                }
            )
        return {"secrets": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Secrets: {str(e)}")


@router.get("/secrets/{name}")
async def get_secret_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get Secret detail (keys only, not values for security)"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        secret = v1.read_namespaced_secret(name, namespace)

        return {
            "kind": "Secret",
            "apiVersion": "v1",
            "metadata": {
                "name": secret.metadata.name,
                "namespace": secret.metadata.namespace,
                "labels": secret.metadata.labels or {},
                "annotations": secret.metadata.annotations or {},
                "uid": secret.metadata.uid,
                "creationTimestamp": secret.metadata.creation_timestamp.isoformat()
                if secret.metadata.creation_timestamp
                else None,
            },
            "type": secret.type,
            "data": secret.data or {},
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting Secret: {str(e)}")


@router.put("/secrets/{name}")
async def edit_secret(
    name: str,
    secret_data: dict,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Edit Secret data"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        secret = v1.read_namespaced_secret(name, namespace)

        if "data" in secret_data:
            secret.data = secret_data["data"]
        if "type" in secret_data:
            secret.type = secret_data["type"]
        if "metadata" in secret_data and "labels" in secret_data["metadata"]:
            secret.metadata.labels = secret_data["metadata"]["labels"]

        updated = v1.patch_namespaced_secret(name, namespace, secret)

        return {
            "status": "updated",
            "name": updated.metadata.name,
            "type": updated.type,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating Secret: {str(e)}")


@router.delete("/secrets/{name}")
async def delete_secret(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a Secret"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        v1.delete_namespaced_secret(name, namespace)

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting Secret: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating Secret: {str(e)}")


# =============================================================================
# HPA (HorizontalPodAutoscaler) ENDPOINTS
# =============================================================================


@router.get("/hpas")
async def list_hpas(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all HPAs in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        autoscaling = k8s.AutoscalingV2Api()
        hpas = autoscaling.list_namespaced_horizontal_pod_autoscaler(namespace)

        result = []
        for hpa in hpas.items:
            result.append(
                {
                    "name": hpa.metadata.name,
                    "namespace": hpa.metadata.namespace,
                    "target": hpa.spec.scale_target_ref.kind,
                    "target_name": hpa.spec.scale_target_ref.name,
                    "min_replicas": hpa.spec.min_replicas,
                    "max_replicas": hpa.spec.max_replicas,
                    "current_replicas": hpa.status.current_replicas
                    if hpa.status
                    else 0,
                    "desired_replicas": hpa.status.desired_replicas
                    if hpa.status
                    else 0,
                    "created": hpa.metadata.creation_timestamp,
                }
            )
        return {"hpas": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing HPAs: {str(e)}")


@router.get("/hpas/{name}")
async def get_hpa_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get HPA detail including scaling metrics"""
    k8s, namespace = get_k8s_context(request)

    try:
        autoscaling = k8s.AutoscalingV2Api()
        hpa = autoscaling.read_namespaced_horizontal_pod_autoscaler(name, namespace)

        return {
            "name": hpa.metadata.name,
            "namespace": hpa.metadata.namespace,
            "labels": hpa.metadata.labels or {},
            "annotations": hpa.metadata.annotations or {},
            "spec": {
                "min_replicas": hpa.spec.min_replicas,
                "max_replicas": hpa.spec.max_replicas,
                "target_cpu_utilization": hpa.spec.target_cpu_utilization_percentage,
                "scale_target": {
                    "kind": hpa.spec.scale_target_ref.kind,
                    "name": hpa.spec.scale_target_ref.name,
                },
            },
            "status": {
                "current_replicas": hpa.status.current_replicas if hpa.status else 0,
                "desired_replicas": hpa.status.desired_replicas if hpa.status else 0,
                "current_cpu_utilization": hpa.status.current_cpu_utilization_percentage
                if hpa.status
                else None,
            },
            "created": hpa.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"HPA '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting HPA: {str(e)}")


@router.put("/hpas/{name}")
async def edit_hpa(
    name: str,
    spec: dict,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Edit HPA scaling specifications"""
    k8s, namespace = get_k8s_context(request)

    try:
        autoscaling = k8s.AutoscalingV2Api()
        hpa = autoscaling.read_namespaced_horizontal_pod_autoscaler(name, namespace)

        # Update spec
        if "min_replicas" in spec:
            hpa.spec.min_replicas = spec["min_replicas"]
        if "max_replicas" in spec:
            hpa.spec.max_replicas = spec["max_replicas"]
        if "target_cpu_utilization_percentage" in spec:
            hpa.spec.target_cpu_utilization_percentage = spec[
                "target_cpu_utilization_percentage"
            ]

        updated = autoscaling.patch_namespaced_horizontal_pod_autoscaler(
            name, namespace, hpa
        )

        return {
            "status": "updated",
            "name": updated.metadata.name,
            "min_replicas": updated.spec.min_replicas,
            "max_replicas": updated.spec.max_replicas,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"HPA '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating HPA: {str(e)}")


# =============================================================================
# RESOURCE QUOTA ENDPOINTS
# =============================================================================


@router.get("/quotas")
async def list_resource_quotas(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all ResourceQuotas in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()
        quotas = core.list_namespaced_resource_quota(namespace)

        result = []
        for quota in quotas.items:
            result.append(
                {
                    "name": quota.metadata.name,
                    "namespace": quota.metadata.namespace,
                    "resources": list(quota.spec.hard.keys())
                    if quota.spec.hard
                    else [],
                    "created": quota.metadata.creation_timestamp,
                }
            )
        return {"quotas": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing ResourceQuotas: {str(e)}"
        )


@router.get("/quotas/{name}")
async def get_resource_quota_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get ResourceQuota detail with hard limits and current usage"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()
        quota = core.read_namespaced_resource_quota(name, namespace)

        return {
            "name": quota.metadata.name,
            "namespace": quota.metadata.namespace,
            "kind": "ResourceQuota",
            "apiVersion": "v1",
            "labels": quota.metadata.labels or {},
            "annotations": quota.metadata.annotations or {},
            "spec": {"hard": quota.spec.hard or {}},
            "status": {"used": quota.status.used if quota.status else {}},
            "created": quota.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"ResourceQuota '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting ResourceQuota: {str(e)}"
        )


# =============================================================================
# LIMIT RANGE ENDPOINTS
# =============================================================================


@router.get("/limitranges")
async def list_limit_ranges(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all LimitRanges in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()
        limits = core.list_namespaced_limit_range(namespace)

        result = []
        for lr in limits.items:
            result.append(
                {
                    "name": lr.metadata.name,
                    "namespace": lr.metadata.namespace,
                    "limits_count": len(lr.spec.limits) if lr.spec.limits else 0,
                    "created": lr.metadata.creation_timestamp,
                }
            )
        return {"limitranges": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing LimitRanges: {str(e)}"
        )


@router.get("/limitranges/{name}")
async def get_limit_range_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get LimitRange detail with all limits"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()
        lr = core.read_namespaced_limit_range(name, namespace)

        return {
            "name": lr.metadata.name,
            "namespace": lr.metadata.namespace,
            "kind": "LimitRange",
            "apiVersion": "v1",
            "labels": lr.metadata.labels or {},
            "annotations": lr.metadata.annotations or {},
            "spec": {"limits": lr.spec.limits or []},
            "created": lr.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"LimitRange '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting LimitRange: {str(e)}"
        )


# =============================================================================
# SERVICE ACCOUNT ENDPOINTS
# =============================================================================


@router.get("/serviceaccounts")
async def list_service_accounts(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all ServiceAccounts in the current namespace or all namespaces"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()

        # Handle all namespaces mode
        if namespace == "_all_" or namespace == "_all":
            sas = core.list_service_account_for_all_namespaces()
        else:
            sas = core.list_namespaced_service_account(namespace)

        return [
            {
                "name": sa.metadata.name,
                "namespace": sa.metadata.namespace,
                "age": sa.metadata.creation_timestamp,
            }
            for sa in sas.items
        ]
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing ServiceAccounts: {str(e)}"
        )


@router.get("/serviceaccounts/{name}")
async def get_service_account_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get ServiceAccount detail"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()
        sa = core.read_namespaced_service_account(name, namespace)

        return {
            "kind": "ServiceAccount",
            "apiVersion": "v1",
            "metadata": {
                "name": sa.metadata.name,
                "namespace": sa.metadata.namespace,
                "uid": str(sa.metadata.uid),
                "labels": sa.metadata.labels or {},
                "annotations": sa.metadata.annotations or {},
                "creationTimestamp": sa.metadata.creation_timestamp.isoformat()
                if sa.metadata.creation_timestamp
                else None,
            },
            "secrets": [{"name": s.name} for s in (sa.secrets or [])],
            "imagePullSecrets": [
                {"name": s.name} for s in (sa.image_pull_secrets or [])
            ],
            "automountServiceAccountToken": sa.automount_service_account_token,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"ServiceAccount '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting ServiceAccount: {str(e)}"
        )


@router.delete("/serviceaccounts/{name}")
async def delete_service_account(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a ServiceAccount"""
    k8s, namespace = get_k8s_context(request)

    try:
        core = k8s.CoreV1Api()
        core.delete_namespaced_service_account(name, namespace)

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"ServiceAccount '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting ServiceAccount: {str(e)}"
        )
