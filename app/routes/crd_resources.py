"""
Custom Resource Definition (CRD) Management Endpoints
Handles: CRD discovery, custom resource instances (namespaced and cluster-scoped)
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from kubernetes.client.rest import ApiException
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging

router = APIRouter(prefix="/api/resources", tags=["crds"])
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
# CRD DISCOVERY ENDPOINTS
# =============================================================================


@router.get("/crds")
async def list_crds(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all Custom Resource Definitions in the cluster"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        apiext = k8s.ApiextensionsV1Api()
        crds = apiext.list_custom_resource_definition()
        logger.info(
            f"CRD list returned {len(crds.items)} items for cluster {cluster_id}, kubeconfig={cluster.get('kubeconfig_path', 'N/A')}"
        )

        result = []
        for crd in crds.items:
            version_names = []
            if crd.spec.versions:
                for ver in crd.spec.versions:
                    version_names.append(ver.name)
            result.append(
                {
                    "name": crd.metadata.name,
                    "group": crd.spec.group,
                    "kind": crd.spec.names.kind,
                    "plural": crd.spec.names.plural,
                    "scope": crd.spec.scope,
                    "versions": version_names,
                    "created": crd.metadata.creation_timestamp,
                }
            )
        return {"crds": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing CRDs: {str(e)}")


@router.delete("/crds/{name}")
async def delete_crd(
    name: str, request: Request, current_user=Depends(require_role(["admin", "edit"]))
):
    """Delete a Custom Resource Definition from the cluster"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        apiext = k8s.ApiextensionsV1Api()
        apiext.delete_custom_resource_definition(name)
        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"CRD '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting CRD: {str(e)}")


@router.get("/crds/{name}")
async def get_crd_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get Custom Resource Definition detail"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        apiext = k8s.ApiextensionsV1Api()
        crd = apiext.read_custom_resource_definition(name)

        versions = []
        if crd.spec.versions:
            for ver in crd.spec.versions:
                versions.append(
                    {"name": ver.name, "served": ver.served, "storage": ver.storage}
                )

        return {
            "name": crd.metadata.name,
            "labels": crd.metadata.labels or {},
            "annotations": crd.metadata.annotations or {},
            "group": crd.spec.group,
            "kind": crd.spec.names.kind,
            "plural": crd.spec.names.plural,
            "singular": crd.spec.names.singular or "",
            "scope": crd.spec.scope,
            "versions": versions,
            "created": crd.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"CRD '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting CRD: {str(e)}")


# =============================================================================
# NAMESPACED CUSTOM RESOURCE ENDPOINTS
# =============================================================================


@router.get("/custom/{group}/{version}/{plural}")
async def list_custom_resources(
    group: str,
    version: str,
    plural: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """List custom resources of a specific type in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        custom_objects = k8s.CustomObjectsApi()
        resources = custom_objects.list_namespaced_custom_object(
            group, version, namespace, plural
        )

        result = []
        for item in resources.get("items", []):
            result.append(
                {
                    "name": item["metadata"]["name"],
                    "namespace": item["metadata"]["namespace"],
                    "kind": item.get("kind", ""),
                    "labels": item["metadata"].get("labels", {}),
                    "created": item["metadata"].get("creationTimestamp", ""),
                }
            )
        return {"custom_resources": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing custom resources: {str(e)}"
        )


@router.delete("/custom/{group}/{version}/{plural}/{name}")
async def delete_custom_resource(
    group: str,
    version: str,
    plural: str,
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a specific custom resource instance in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        custom_objects = k8s.CustomObjectsApi()
        custom_objects.delete_namespaced_custom_object(
            group, version, namespace, plural, name
        )
        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"Custom resource '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting custom resource: {str(e)}"
        )


@router.get("/custom/{group}/{version}/{plural}/{name}")
async def get_custom_resource(
    group: str,
    version: str,
    plural: str,
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get a specific custom resource instance in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        custom_objects = k8s.CustomObjectsApi()
        resource = custom_objects.get_namespaced_custom_object(
            group, version, namespace, plural, name
        )

        return {
            "name": resource["metadata"]["name"],
            "namespace": resource["metadata"]["namespace"],
            "kind": resource.get("kind", ""),
            "api_version": resource.get("apiVersion", ""),
            "labels": resource["metadata"].get("labels", {}),
            "annotations": resource["metadata"].get("annotations", {}),
            "spec": resource.get("spec", {}),
            "status": resource.get("status", {}),
            "created": resource["metadata"].get("creationTimestamp", ""),
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"Custom resource '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting custom resource: {str(e)}"
        )


# =============================================================================
# CLUSTER-SCOPED CUSTOM RESOURCE ENDPOINTS
# =============================================================================


@router.get("/custom-cluster/{group}/{version}/{plural}")
async def list_cluster_custom_resources(
    group: str,
    version: str,
    plural: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """List cluster-scoped custom resources of a specific type"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        custom_objects = k8s.CustomObjectsApi()
        resources = custom_objects.list_cluster_custom_object(group, version, plural)

        result = []
        for item in resources.get("items", []):
            result.append(
                {
                    "name": item["metadata"]["name"],
                    "kind": item.get("kind", ""),
                    "labels": item["metadata"].get("labels", {}),
                    "created": item["metadata"].get("creationTimestamp", ""),
                }
            )
        return {"custom_resources": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing cluster custom resources: {str(e)}"
        )


@router.delete("/custom-cluster/{group}/{version}/{plural}/{name}")
async def delete_cluster_custom_resource(
    group: str,
    version: str,
    plural: str,
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a specific cluster-scoped custom resource instance"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        custom_objects = k8s.CustomObjectsApi()
        custom_objects.delete_cluster_custom_object(group, version, plural, name)
        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"Cluster custom resource '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting cluster custom resource: {str(e)}"
        )


@router.get("/custom-cluster/{group}/{version}/{plural}/{name}")
async def get_cluster_custom_resource(
    group: str,
    version: str,
    plural: str,
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get a specific cluster-scoped custom resource instance"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            raise HTTPException(404, "Cluster not found")
        k8s = load_k8s_client(cluster["kubeconfig_path"])

        custom_objects = k8s.CustomObjectsApi()
        resource = custom_objects.get_cluster_custom_object(
            group, version, plural, name
        )

        return {
            "name": resource["metadata"]["name"],
            "kind": resource.get("kind", ""),
            "api_version": resource.get("apiVersion", ""),
            "labels": resource["metadata"].get("labels", {}),
            "annotations": resource["metadata"].get("annotations", {}),
            "spec": resource.get("spec", {}),
            "status": resource.get("status", {}),
            "created": resource["metadata"].get("creationTimestamp", ""),
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"Cluster custom resource '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting cluster custom resource: {str(e)}"
        )
