"""
Storage Resource Management Endpoints
Handles: PersistentVolumes, PersistentVolumeClaims, StorageClasses
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from kubernetes.client.rest import ApiException
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging

router = APIRouter(prefix="/api/resources/storage", tags=["storage"])
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
# PERSISTENT VOLUME ENDPOINTS
# =============================================================================


@router.get("/persistentvolumes")
async def list_persistent_volumes(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all PersistentVolumes in the cluster"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        v1 = k8s.CoreV1Api()
        persistentvolumes = v1.list_persistent_volume()

        result = []
        for pv in persistentvolumes.items:
            capacity = "0"
            if pv.spec.capacity and "storage" in pv.spec.capacity:
                capacity = pv.spec.capacity["storage"]

            result.append(
                {
                    "name": pv.metadata.name,
                    "capacity": capacity,
                    "access_modes": pv.spec.access_modes or [],
                    "status": pv.status.phase if pv.status else "Unknown",
                    "storage_class": pv.spec.storage_class_name or "default",
                    "created": pv.metadata.creation_timestamp,
                }
            )
        return {"persistentvolumes": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing PersistentVolumes: {str(e)}"
        )


@router.get("/persistentvolumes/{name}")
async def get_persistent_volume_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get PersistentVolume detail"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        v1 = k8s.CoreV1Api()
        pv = v1.read_persistent_volume(name)

        return {
            "kind": "PersistentVolume",
            "apiVersion": "v1",
            "metadata": {
                "name": pv.metadata.name,
                "labels": pv.metadata.labels or {},
                "annotations": pv.metadata.annotations or {},
                "uid": str(pv.metadata.uid) if pv.metadata.uid else None,
                "creationTimestamp": pv.metadata.creation_timestamp.isoformat()
                if pv.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "capacity": dict(pv.spec.capacity) if pv.spec.capacity else {},
                "accessModes": pv.spec.access_modes or [],
                "persistentVolumeReclaimPolicy": pv.spec.persistent_volume_reclaim_policy
                or "Delete",
                "storageClassName": pv.spec.storage_class_name or "default",
                "volumeMode": pv.spec.volume_mode or "Filesystem",
            },
            "status": {
                "phase": pv.status.phase if pv.status else "Unknown",
            },
            "age": str(pv.metadata.creation_timestamp)
            if pv.metadata.creation_timestamp
            else None,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"PersistentVolume '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting PersistentVolume: {str(e)}"
        )


@router.delete("/persistentvolumes/{name}")
async def delete_persistent_volume(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a PersistentVolume"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = (
            current_user.get("email")
            if isinstance(current_user, dict)
            else str(current_user)
        )
        namespace = request.session.get("active_namespace", "default")
        yaml_before = _fetch_resource_yaml(k8s, "pvs", name, namespace)

        v1 = k8s.CoreV1Api()
        v1.delete_persistent_volume(name)

        save_resource_snapshot(
            request=request,
            resource_type="pvs",
            resource_name=name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"PersistentVolume '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting PersistentVolume: {str(e)}"
        )


# =============================================================================
# PERSISTENT VOLUME CLAIM ENDPOINTS
# =============================================================================


@router.get("/persistentvolumeclaims")
async def list_persistent_volume_claims(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all PersistentVolumeClaims in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        persistentvolumeclaims = v1.list_namespaced_persistent_volume_claim(namespace)

        result = []
        for pvc in persistentvolumeclaims.items:
            requested_capacity = "0"
            if pvc.spec.resources and pvc.spec.resources.requests:
                requested_capacity = pvc.spec.resources.requests.get("storage", "0")

            result.append(
                {
                    "name": pvc.metadata.name,
                    "namespace": pvc.metadata.namespace,
                    "status": pvc.status.phase if pvc.status else "Unknown",
                    "volume": pvc.spec.volume_name or "",
                    "capacity": requested_capacity,
                    "access_modes": pvc.spec.access_modes or [],
                    "storage_class": pvc.spec.storage_class_name or "default",
                    "created": pvc.metadata.creation_timestamp,
                }
            )
        return {"persistentvolumeclaims": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing PersistentVolumeClaims: {str(e)}"
        )


@router.get("/persistentvolumeclaims/{name}")
async def get_persistent_volume_claim_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get PersistentVolumeClaim detail"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        pvc = v1.read_namespaced_persistent_volume_claim(name, namespace)

        return {
            "kind": "PersistentVolumeClaim",
            "apiVersion": "v1",
            "metadata": {
                "name": pvc.metadata.name,
                "namespace": pvc.metadata.namespace,
                "labels": pvc.metadata.labels or {},
                "annotations": pvc.metadata.annotations or {},
                "uid": str(pvc.metadata.uid) if pvc.metadata.uid else None,
                "creationTimestamp": pvc.metadata.creation_timestamp.isoformat()
                if pvc.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "accessModes": pvc.spec.access_modes or [],
                "storageClassName": pvc.spec.storage_class_name or "default",
                "volumeName": pvc.spec.volume_name or "",
                "resources": {
                    "requests": dict(pvc.spec.resources.requests)
                    if pvc.spec.resources and pvc.spec.resources.requests
                    else {}
                },
            },
            "status": {
                "phase": pvc.status.phase if pvc.status else "Unknown",
                "capacity": dict(pvc.status.capacity)
                if pvc.status and pvc.status.capacity
                else {},
            },
            "age": str(pvc.metadata.creation_timestamp)
            if pvc.metadata.creation_timestamp
            else None,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"PersistentVolumeClaim '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting PersistentVolumeClaim: {str(e)}"
        )


@router.delete("/persistentvolumeclaims/{name}")
async def delete_persistent_volume_claim(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a PersistentVolumeClaim"""
    k8s, namespace = get_k8s_context(request)

    try:
        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = (
            current_user.get("email")
            if isinstance(current_user, dict)
            else str(current_user)
        )
        yaml_before = _fetch_resource_yaml(k8s, "pvcs", name, namespace)

        v1 = k8s.CoreV1Api()
        v1.delete_namespaced_persistent_volume_claim(name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="pvcs",
            resource_name=name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"PersistentVolumeClaim '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting PersistentVolumeClaim: {str(e)}"
        )


# =============================================================================
# STORAGE CLASS ENDPOINTS
# =============================================================================


@router.get("/storageclasses")
async def list_storage_classes(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all StorageClasses in the cluster"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        storage = k8s.StorageV1Api()
        storageclasses = storage.list_storage_class()

        result = []
        for sc in storageclasses.items:
            result.append(
                {
                    "name": sc.metadata.name,
                    "provisioner": sc.provisioner,
                    "reclaim_policy": sc.reclaim_policy or "Delete",
                    "volume_binding_mode": sc.volume_binding_mode or "Immediate",
                    "parameters_count": len(sc.parameters) if sc.parameters else 0,
                    "created": sc.metadata.creation_timestamp,
                }
            )
        return {"storageclasses": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing StorageClasses: {str(e)}"
        )


@router.get("/storageclasses/{name}")
async def get_storage_class_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get StorageClass detail"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        storage = k8s.StorageV1Api()
        sc = storage.read_storage_class(name)

        return {
            "name": sc.metadata.name,
            "labels": sc.metadata.labels or {},
            "annotations": sc.metadata.annotations or {},
            "provisioner": sc.provisioner,
            "reclaim_policy": sc.reclaim_policy or "Delete",
            "volume_binding_mode": sc.volume_binding_mode or "Immediate",
            "parameters": sc.parameters or {},
            "allow_volume_expansion": sc.allow_volume_expansion
            if hasattr(sc, "allow_volume_expansion")
            else False,
            "created": sc.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"StorageClass '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting StorageClass: {str(e)}"
        )
