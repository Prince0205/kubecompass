"""
Namespace Request API Routes

Provides REST API endpoints for namespace requests with approval workflow.
Users can request namespaces with resource quotas, and admins can approve/reject.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.auth.rbac import require_role
from app.db import namespace_requests, clusters
from bson import ObjectId
from kubernetes import client as kclient
from app.k8s.loader import load_k8s_client
import logging

router = APIRouter(prefix="/api/namespace-requests", tags=["namespace-requests"])
logger = logging.getLogger(__name__)


class NamespaceRequestCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    cpu_limit: Optional[str] = "2"
    memory_limit: Optional[str] = "4Gi"
    storage_limit: Optional[str] = "10Gi"
    pods_limit: Optional[int] = 10
    services_limit: Optional[int] = 10
    configmaps_limit: Optional[int] = 10
    secrets_limit: Optional[int] = 10


class NamespaceRequestApprove(BaseModel):
    action: str  # "approve" or "reject"
    comment: Optional[str] = ""


@router.get("")
def list_namespace_requests(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all namespace requests for the current cluster."""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(status_code=400, detail="No cluster selected")

    reqs = list(
        namespace_requests.find({"cluster_id": cluster_id}).sort("created_at", -1)
    )

    return [
        {
            "id": str(r["_id"]),
            "name": r["name"],
            "description": r.get("description", ""),
            "cpu_limit": r.get("cpu_limit", "2"),
            "memory_limit": r.get("memory_limit", "4Gi"),
            "storage_limit": r.get("storage_limit", "10Gi"),
            "pods_limit": r.get("pods_limit", 10),
            "services_limit": r.get("services_limit", 10),
            "configmaps_limit": r.get("configmaps_limit", 10),
            "secrets_limit": r.get("secrets_limit", 10),
            "requested_by": r.get("requested_by", ""),
            "status": r.get("status", "pending"),
            "comment": r.get("comment", ""),
            "created_at": r.get("created_at", "").isoformat()
            if r.get("created_at")
            else "",
            "updated_at": r.get("updated_at", "").isoformat()
            if r.get("updated_at")
            else "",
        }
        for r in reqs
    ]


@router.post("")
def create_namespace_request(
    payload: NamespaceRequestCreate,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Create a new namespace request."""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(status_code=400, detail="No cluster selected")

    # Check if namespace already exists
    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if cluster:
            k8s = load_k8s_client(cluster.get("kubeconfig_path"))
            v1 = k8s.CoreV1Api()
            existing = v1.list_namespace().items
            if any(ns.metadata.name == payload.name for ns in existing):
                raise HTTPException(status_code=400, detail="Namespace already exists")
    except Exception as e:
        logger.error(f"Error checking namespace: {e}")

    # Check if request already exists
    existing = namespace_requests.find_one(
        {"cluster_id": cluster_id, "name": payload.name, "status": "pending"}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Request already pending for this namespace"
        )

    req = {
        "cluster_id": cluster_id,
        "name": payload.name,
        "description": payload.description,
        "cpu_limit": payload.cpu_limit,
        "memory_limit": payload.memory_limit,
        "storage_limit": payload.storage_limit,
        "pods_limit": payload.pods_limit,
        "services_limit": payload.services_limit,
        "configmaps_limit": payload.configmaps_limit,
        "secrets_limit": payload.secrets_limit,
        "requested_by": user.get("email", "unknown"),
        "status": "pending",
        "comment": "",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = namespace_requests.insert_one(req)
    return {"id": str(result.inserted_id), "status": "pending"}


@router.post("/{request_id}/approve")
def approve_namespace_request(
    request_id: str,
    payload: NamespaceRequestApprove,
    request: Request,
    user=Depends(require_role(["admin"])),
):
    """Approve or reject a namespace request."""
    try:
        req_obj_id = ObjectId(request_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    req = namespace_requests.find_one({"_id": req_obj_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Request already processed")

    cluster_id = req.get("cluster_id")
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    action = payload.action.lower()

    if action == "approve":
        try:
            k8s = load_k8s_client(cluster.get("kubeconfig_path"))
            v1 = k8s.CoreV1Api()

            # Create namespace
            from kubernetes.client import (
                V1Namespace,
                V1ObjectMeta,
                V1ResourceRequirements,
            )

            ns = V1Namespace(
                metadata=V1ObjectMeta(name=req["name"]),
                # ResourceQuota will be created separately
            )
            v1.create_namespace(ns)

            # Create ResourceQuota
            quota = k8s.V1ResourceQuota(
                metadata=V1ObjectMeta(name=f"{req['name']}-quota"),
                spec={
                    "hard": {
                        "cpu": req.get("cpu_limit", "2"),
                        "memory": req.get("memory_limit", "4Gi"),
                        "requests.storage": req.get("storage_limit", "10Gi"),
                        "pods": str(req.get("pods_limit", 10)),
                        "services": str(req.get("services_limit", 10)),
                        "configmaps": str(req.get("configmaps_limit", 10)),
                        "secrets": str(req.get("secrets_limit", 10)),
                    }
                },
            )
            v1.create_namespaced_resource_quota(namespace=req["name"], body=quota)

            namespace_requests.update_one(
                {"_id": req_obj_id},
                {
                    "$set": {
                        "status": "approved",
                        "comment": payload.comment or "Approved",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            return {
                "status": "approved",
                "message": f"Namespace {req['name']} created successfully",
            }

        except Exception as e:
            logger.error(f"Error creating namespace: {e}")
            namespace_requests.update_one(
                {"_id": req_obj_id},
                {
                    "$set": {
                        "status": "failed",
                        "comment": f"Error: {str(e)}",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to create namespace: {str(e)}"
            )

    elif action == "reject":
        namespace_requests.update_one(
            {"_id": req_obj_id},
            {
                "$set": {
                    "status": "rejected",
                    "comment": payload.comment or "Rejected",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return {"status": "rejected", "message": "Request rejected"}

    else:
        raise HTTPException(
            status_code=400, detail="Invalid action. Use 'approve' or 'reject'"
        )


@router.delete("/{request_id}")
def delete_namespace_request(
    request_id: str, request: Request, user=Depends(require_role(["admin"]))
):
    """Delete a namespace request."""
    try:
        req_obj_id = ObjectId(request_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request ID")

    result = namespace_requests.delete_one({"_id": req_obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Request not found")

    return {"status": "deleted"}
