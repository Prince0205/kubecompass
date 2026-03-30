"""
Resource History Routes

Provides REST API endpoints for resource change history:
- List history entries with filters
- Get specific snapshot YAML
- Diff between two snapshots
- Restore a previous snapshot

Snapshots are captured on mutations (apply, scale, delete) via save_resource_snapshot().
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.db import resource_history, clusters
from app.k8s.loader import load_k8s_client
from bson import ObjectId
from datetime import datetime, timezone
import yaml
import json
import difflib
import logging

router = APIRouter(prefix="/api/history")
logger = logging.getLogger(__name__)


def save_resource_snapshot(
    request: Request,
    resource_type: str,
    resource_name: str,
    operation: str,
    user_email: str = "",
    yaml_before: str = None,
    yaml_after: str = None,
):
    """
    Save a resource snapshot to the history collection.

    Call this from mutation endpoints to record changes.
    """
    try:
        namespace = request.session.get("active_namespace", "default")
        cluster_id = request.session.get("active_cluster", "")

        if not cluster_id:
            logger.error("save_resource_snapshot: no active_cluster in session")
            return

        doc = {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "namespace": namespace,
            "cluster_id": cluster_id,
            "operation": operation,
            "user": user_email,
            "yaml_before": yaml_before,
            "yaml_after": yaml_after,
            "timestamp": datetime.now(timezone.utc),
        }
        resource_history.insert_one(doc)
        logger.info(
            f"Saved history snapshot: {operation} {resource_type}/{resource_name}"
        )
    except Exception as e:
        logger.error(f"Failed to save resource snapshot: {e}", exc_info=True)


def _get_k8s_context(request: Request):
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


def _fetch_resource_yaml(k8s, resource_type, resource_name, namespace):
    """Fetch the current YAML of a resource from the cluster."""
    try:
        api_client = k8s.ApiClient()
        base = api_client.configuration.host.rstrip("/")
        from urllib.parse import urlencode

        # Build the API URL based on resource type
        api_paths = {
            "deployments": f"/apis/apps/v1/namespaces/{namespace}/deployments/{resource_name}",
            "statefulsets": f"/apis/apps/v1/namespaces/{namespace}/statefulsets/{resource_name}",
            "daemonsets": f"/apis/apps/v1/namespaces/{namespace}/daemonsets/{resource_name}",
            "replicasets": f"/apis/apps/v1/namespaces/{namespace}/replicasets/{resource_name}",
            "pods": f"/api/v1/namespaces/{namespace}/pods/{resource_name}",
            "services": f"/api/v1/namespaces/{namespace}/services/{resource_name}",
            "configmaps": f"/api/v1/namespaces/{namespace}/configmaps/{resource_name}",
            "secrets": f"/api/v1/namespaces/{namespace}/secrets/{resource_name}",
            "jobs": f"/apis/batch/v1/namespaces/{namespace}/jobs/{resource_name}",
            "cronjobs": f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{resource_name}",
            "ingresses": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/ingresses/{resource_name}",
            "pvcs": f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{resource_name}",
            "pvc": f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{resource_name}",
            "pvs": f"/api/v1/persistentvolumes/{resource_name}",
            "pv": f"/api/v1/persistentvolumes/{resource_name}",
            "serviceaccounts": f"/api/v1/namespaces/{namespace}/serviceaccounts/{resource_name}",
            "roles": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/roles/{resource_name}",
            "clusterroles": f"/apis/rbac.authorization.k8s.io/v1/clusterroles/{resource_name}",
            "rolebindings": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/rolebindings/{resource_name}",
            "clusterrolebindings": f"/apis/rbac.authorization.k8s.io/v1/clusterrolebindings/{resource_name}",
            "hpas": f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{resource_name}",
            "networkpolicies": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/networkpolicies/{resource_name}",
            "quotas": f"/api/v1/namespaces/{namespace}/resourcequotas/{resource_name}",
            "limitranges": f"/api/v1/namespaces/{namespace}/limitranges/{resource_name}",
            "storageclasses": f"/apis/storage.k8s.io/v1/storageclasses/{resource_name}",
        }

        api_path = api_paths.get(resource_type)
        if not api_path:
            logger.warning(f"Unknown resource type for YAML fetch: {resource_type}")
            return None

        url = f"{base}{api_path}"
        headers = {
            "Accept": "application/json",
        }

        resp = api_client.rest_client.pool_manager.request("GET", url, headers=headers)
        resp_status = resp.status if hasattr(resp, "status") else 200

        if resp_status >= 400:
            logger.warning(
                f"Failed to fetch YAML for {resource_type}/{resource_name}: HTTP {resp_status}"
            )
            return None

        resp_bytes = resp.data if hasattr(resp, "data") else resp.read()
        resp_text = (
            resp_bytes.decode("utf-8")
            if hasattr(resp_bytes, "decode")
            else str(resp_bytes)
        )

        # Convert JSON to YAML for storage
        import json as json_mod
        import yaml as yaml_mod

        try:
            parsed = json_mod.loads(resp_text)
            return yaml_mod.safe_dump(parsed, sort_keys=False)
        except (json_mod.JSONDecodeError, Exception):
            # Already YAML or can't parse - return as-is
            return resp_text
    except Exception as e:
        logger.warning(
            f"Failed to fetch resource YAML for {resource_type}/{resource_name}: {e}"
        )
        return None


@router.get("")
def list_history(
    request: Request,
    resource_type: str = Query(None),
    resource_name: str = Query(None),
    namespace: str = Query(None),
    operation: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    List resource history entries.

    Query params:
    - resource_type: filter by resource type (e.g. 'deployments')
    - resource_name: filter by resource name
    - namespace: filter by namespace
    - operation: filter by operation (apply, scale, delete, update-image, etc.)
    - limit: max entries to return (default 50)
    """
    try:
        cluster_id = request.session.get("active_cluster")
        if not cluster_id:
            raise HTTPException(400, "No active cluster selected")

        query = {"cluster_id": cluster_id}
        if resource_type:
            query["resource_type"] = resource_type
        if resource_name:
            query["resource_name"] = resource_name
        if namespace and namespace != "_all":
            query["namespace"] = namespace
        if operation:
            query["operation"] = operation

        cursor = (
            resource_history.find(
                query,
                {
                    "yaml_before": 0,
                    "yaml_after": 0,
                },
            )
            .sort("timestamp", -1)
            .limit(limit)
        )

        entries = []
        for doc in cursor:
            entries.append(
                {
                    "id": str(doc["_id"]),
                    "resource_type": doc.get("resource_type", ""),
                    "resource_name": doc.get("resource_name", ""),
                    "namespace": doc.get("namespace", ""),
                    "operation": doc.get("operation", ""),
                    "user": doc.get("user", ""),
                    "timestamp": doc.get("timestamp", "").isoformat()
                    if doc.get("timestamp")
                    else "",
                    "has_yaml_before": bool(doc.get("yaml_before")),
                    "has_yaml_after": bool(doc.get("yaml_after")),
                }
            )

        return {
            "entries": entries,
            "total": len(entries),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing history: {e}")
        raise HTTPException(500, f"Failed to list history: {str(e)}")


@router.get("/types")
def list_history_types(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """List all resource types that have history entries."""
    try:
        cluster_id = request.session.get("active_cluster")
        if not cluster_id:
            raise HTTPException(400, "No active cluster selected")

        pipeline = [
            {"$match": {"cluster_id": cluster_id}},
            {
                "$group": {
                    "_id": "$resource_type",
                    "count": {"$sum": 1},
                    "latest": {"$max": "$timestamp"},
                }
            },
            {"$sort": {"latest": -1}},
        ]

        results = list(resource_history.aggregate(pipeline))
        types = [
            {
                "resource_type": r["_id"],
                "count": r["count"],
                "latest": r["latest"].isoformat() if r.get("latest") else "",
            }
            for r in results
            if r["_id"]
        ]

        return {"types": types}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing history types: {e}")
        raise HTTPException(500, f"Failed to list history types: {str(e)}")


@router.get("/{entry_id}")
def get_history_entry(
    entry_id: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get a specific history entry including YAML snapshots."""
    try:
        doc = resource_history.find_one({"_id": ObjectId(entry_id)})
        if not doc:
            raise HTTPException(404, "History entry not found")

        return {
            "id": str(doc["_id"]),
            "resource_type": doc.get("resource_type", ""),
            "resource_name": doc.get("resource_name", ""),
            "namespace": doc.get("namespace", ""),
            "operation": doc.get("operation", ""),
            "user": doc.get("user", ""),
            "yaml_before": doc.get("yaml_before", ""),
            "yaml_after": doc.get("yaml_after", ""),
            "timestamp": doc.get("timestamp", "").isoformat()
            if doc.get("timestamp")
            else "",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history entry: {e}")
        raise HTTPException(500, f"Failed to get history entry: {str(e)}")


@router.get("/{entry_id}/diff")
def get_history_diff(
    entry_id: str,
    request: Request,
    compare_with: str = Query(
        None, description="ID of another history entry to compare with"
    ),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Get a diff for a history entry.

    If compare_with is provided, diff between the two entries.
    Otherwise, diff yaml_before and yaml_after of the single entry.
    """
    try:
        entry = resource_history.find_one({"_id": ObjectId(entry_id)})
        if not entry:
            raise HTTPException(404, "History entry not found")

        if compare_with:
            other = resource_history.find_one({"_id": ObjectId(compare_with)})
            if not other:
                raise HTTPException(404, "Comparison entry not found")
            before_yaml = other.get("yaml_after") or other.get("yaml_before") or ""
            after_yaml = entry.get("yaml_after") or entry.get("yaml_before") or ""
            before_label = f"{other.get('resource_type', '')}/{other.get('resource_name', '')} ({other.get('timestamp', '').isoformat() if other.get('timestamp') else ''})"
            after_label = f"{entry.get('resource_type', '')}/{entry.get('resource_name', '')} ({entry.get('timestamp', '').isoformat() if entry.get('timestamp') else ''})"
        else:
            before_yaml = entry.get("yaml_before") or ""
            after_yaml = entry.get("yaml_after") or ""
            before_label = "Before"
            after_label = "After"

        before_lines = before_yaml.splitlines(keepends=True)
        after_lines = after_yaml.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=before_label,
                tofile=after_label,
                lineterm="",
            )
        )

        # Also generate side-by-side diff
        side_by_side = list(difflib.ndiff(before_lines, after_lines))

        return {
            "entry_id": entry_id,
            "compare_with": compare_with,
            "diff": "".join(diff),
            "diff_lines": diff,
            "side_by_side_lines": side_by_side,
            "before_label": before_label,
            "after_label": after_label,
            "resource_type": entry.get("resource_type", ""),
            "resource_name": entry.get("resource_name", ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating diff: {e}")
        raise HTTPException(500, f"Failed to generate diff: {str(e)}")


@router.post("/{entry_id}/restore")
def restore_history_entry(
    entry_id: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """
    Restore a resource to the state captured in a history entry.

    Uses the Kubernetes API to get the current resource, extracts the spec from the
    snapshot, and applies it via server-side apply.
    """
    try:
        entry = resource_history.find_one({"_id": ObjectId(entry_id)})
        if not entry:
            raise HTTPException(404, "History entry not found")

        yaml_content = entry.get("yaml_before") or entry.get("yaml_after")
        if not yaml_content:
            raise HTTPException(400, "No YAML snapshot available for restore")

        resource_type = entry.get("resource_type", "")
        resource_name = entry.get("resource_name", "")
        namespace = entry.get("namespace", "default")

        k8s, _ = _get_k8s_context(request)

        # Parse the snapshot YAML
        try:
            snap_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise HTTPException(400, f"Invalid YAML in snapshot: {e}")

        if not isinstance(snap_data, dict):
            raise HTTPException(400, "Snapshot YAML is not a valid resource object")

        # Ensure apiVersion and kind are present
        api_version = snap_data.get("apiVersion")
        kind = snap_data.get("kind")

        if not api_version or not kind:
            # Try to fetch the current resource to get apiVersion/kind
            api_client = k8s.ApiClient()
            base = api_client.configuration.host.rstrip("")

            _api_resource_map = {
                "deployments": ("apis/apps/v1", "Deployment"),
                "statefulsets": ("apis/apps/v1", "StatefulSet"),
                "daemonsets": ("apis/apps/v1", "DaemonSet"),
                "replicasets": ("apis/apps/v1", "ReplicaSet"),
                "pods": ("api/v1", "Pod"),
                "services": ("api/v1", "Service"),
                "configmaps": ("api/v1", "ConfigMap"),
                "secrets": ("api/v1", "Secret"),
                "jobs": ("apis/batch/v1", "Job"),
                "cronjobs": ("apis/batch/v1", "CronJob"),
                "ingresses": ("apis/networking.k8s.io/v1", "Ingress"),
                "pvcs": ("api/v1", "PersistentVolumeClaim"),
                "pvs": ("api/v1", "PersistentVolume"),
                "serviceaccounts": ("api/v1", "ServiceAccount"),
                "hpas": ("apis/autoscaling/v2", "HorizontalPodAutoscaler"),
                "networkpolicies": ("apis/networking.k8s.io/v1", "NetworkPolicy"),
                "quotas": ("api/v1", "ResourceQuota"),
                "limitranges": ("api/v1", "LimitRange"),
                "roles": ("apis/rbac.authorization.k8s.io/v1", "Role"),
                "rolebindings": ("apis/rbac.authorization.k8s.io/v1", "RoleBinding"),
                "clusterroles": ("apis/rbac.authorization.k8s.io/v1", "ClusterRole"),
                "clusterrolebindings": (
                    "apis/rbac.authorization.k8s.io/v1",
                    "ClusterRoleBinding",
                ),
                "storageclasses": ("apis/storage.k8s.io/v1", "StorageClass"),
            }

            type_info = _api_resource_map.get(resource_type)
            if type_info:
                api_prefix, k8s_kind = type_info
                if resource_type in (
                    "pvs",
                    "storageclasses",
                    "clusterroles",
                    "clusterrolebindings",
                ):
                    fetch_url = f"{base}/{api_prefix}/{resource_type}/{resource_name}"
                else:
                    fetch_url = f"{base}/{api_prefix}/namespaces/{namespace}/{resource_type}/{resource_name}"

                try:
                    resp = api_client.rest_client.pool_manager.request(
                        "GET", fetch_url, headers={"Accept": "application/json"}
                    )
                    if hasattr(resp, "status") and resp.status < 400:
                        resp_bytes = resp.data if hasattr(resp, "data") else resp.read()
                        import json as json_mod

                        current = json_mod.loads(resp_bytes.decode("utf-8"))
                        api_version = current.get("apiVersion")
                        kind = current.get("kind")
                except Exception:
                    pass

            if not api_version or not kind:
                # Use defaults from the type map
                if type_info:
                    api_version = type_info[0].replace("apis/", "").replace("api/", "")
                    kind = type_info[1]
                else:
                    raise HTTPException(
                        400,
                        "Snapshot YAML is missing apiVersion and kind, and could not fetch current resource",
                    )

        # Build the apply payload from the snapshot
        def clean_for_apply(obj):
            if not isinstance(obj, dict):
                return obj
            result = {}
            skip_fields = {
                "status",
                "managedFields",
                "resourceVersion",
                "uid",
                "creationTimestamp",
                "generation",
                "age",
                "selfLink",
                "deletionTimestamp",
                "deletionGracePeriodSeconds",
                "initializers",
                "finalizers",
                "clusterName",
                "namespace",
            }
            for k, v in obj.items():
                if k in skip_fields:
                    continue
                if isinstance(v, dict):
                    result[k] = clean_for_apply(v)
                elif isinstance(v, list):
                    result[k] = [clean_for_apply(item) for item in v]
                else:
                    result[k] = v
            return result

        cleaned = clean_for_apply(snap_data)
        # Always set apiVersion, kind, and name from our reliable sources
        cleaned["apiVersion"] = api_version
        cleaned["kind"] = kind
        if "metadata" not in cleaned:
            cleaned["metadata"] = {}
        cleaned["metadata"]["name"] = resource_name

        yaml_to_apply = yaml.safe_dump(cleaned, sort_keys=False)

        # Apply via server-side apply
        api_client = k8s.ApiClient()
        base = api_client.configuration.host.rstrip("")

        api_paths = {
            "deployments": f"/apis/apps/v1/namespaces/{namespace}/deployments/{resource_name}",
            "statefulsets": f"/apis/apps/v1/namespaces/{namespace}/statefulsets/{resource_name}",
            "daemonsets": f"/apis/apps/v1/namespaces/{namespace}/daemonsets/{resource_name}",
            "pods": f"/api/v1/namespaces/{namespace}/pods/{resource_name}",
            "services": f"/api/v1/namespaces/{namespace}/services/{resource_name}",
            "configmaps": f"/api/v1/namespaces/{namespace}/configmaps/{resource_name}",
            "secrets": f"/api/v1/namespaces/{namespace}/secrets/{resource_name}",
            "jobs": f"/apis/batch/v1/namespaces/{namespace}/jobs/{resource_name}",
            "cronjobs": f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{resource_name}",
            "ingresses": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/ingresses/{resource_name}",
            "pvcs": f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{resource_name}",
            "pvs": f"/api/v1/persistentvolumes/{resource_name}",
            "replicasets": f"/apis/apps/v1/namespaces/{namespace}/replicasets/{resource_name}",
            "serviceaccounts": f"/api/v1/namespaces/{namespace}/serviceaccounts/{resource_name}",
            "roles": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/roles/{resource_name}",
            "rolebindings": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/rolebindings/{resource_name}",
            "hpas": f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{resource_name}",
            "networkpolicies": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/networkpolicies/{resource_name}",
            "quotas": f"/api/v1/namespaces/{namespace}/resourcequotas/{resource_name}",
            "limitranges": f"/api/v1/namespaces/{namespace}/limitranges/{resource_name}",
        }

        api_path = api_paths.get(resource_type)
        if not api_path:
            raise HTTPException(400, f"Cannot restore resource type: {resource_type}")

        from urllib.parse import urlencode

        url = f"{base}{api_path}?{urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
        headers = {
            "Content-Type": "application/apply-patch+yaml",
            "Accept": "application/json",
        }

        resp = api_client.rest_client.pool_manager.request(
            "PATCH",
            url,
            body=yaml_to_apply.encode("utf-8"),
            headers=headers,
        )

        resp_status = resp.status if hasattr(resp, "status") else 200
        if resp_status >= 400:
            resp_data = resp.data if hasattr(resp, "data") else b""
            error_msg = resp_data.decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=resp_status, detail=f"Restore failed: {error_msg}"
            )

        # Record the restore as a new history entry
        user_email = user.get("email") if isinstance(user, dict) else str(user)
        restored_yaml = _fetch_resource_yaml(
            k8s, resource_type, resource_name, namespace
        )
        save_resource_snapshot(
            request=request,
            resource_type=resource_type,
            resource_name=resource_name,
            operation="restore",
            user_email=user_email,
            yaml_before=yaml_content,
            yaml_after=restored_yaml,
        )

        return {
            "status": "restored",
            "resource_type": resource_type,
            "resource_name": resource_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring history entry: {e}")
        raise HTTPException(500, f"Failed to restore: {str(e)}")
