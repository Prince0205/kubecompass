from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from bson import ObjectId
import logging

from app.auth.rbac import require_role
from app.db import namespace_requests, clusters
from app.k8s.loader import load_k8s_client
from app.k8s.namespace import provision_namespace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

@router.get("/requests")
def approval_page(
    request: Request,
    user=Depends(require_role(["admin"]))
):
    pending = list(namespace_requests.find({"status": "pending"}))

    return templates.TemplateResponse(
        "admin_requests.html",
        {
            "request": request,
            "user": user,
            "requests": pending
        }
    )

@router.get("/requests/approve/{req_id}")
def approve_request(
    req_id: str,
    request: Request,
    user=Depends(require_role(["admin"]))
):
    try:
        req = namespace_requests.find_one({"_id": ObjectId(req_id)})
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        cluster = clusters.find_one({"_id": ObjectId(req["cluster_id"])})
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")

        k8s = load_k8s_client(cluster["kubeconfig_path"])
        v1 = k8s.CoreV1Api()
        rbac = k8s.RbacAuthorizationV1Api()

        provision_namespace(
            v1,
            rbac,
            req["namespace"],
            req["requested_by"],
            req["cpu"],
            req["memory"]
        )

        namespace_requests.update_one(
            {"_id": ObjectId(req_id)},
            {"$set": {"status": "approved"}}
        )

        return RedirectResponse("/admin/requests", status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving request {req_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve request: {str(e)}")

@router.get("/requests/reject/{req_id}")
def reject_request(
    req_id: str,
    user=Depends(require_role(["admin"]))
):
    try:
        req = namespace_requests.find_one({"_id": ObjectId(req_id)})
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        namespace_requests.update_one(
            {"_id": ObjectId(req_id)},
            {"$set": {"status": "rejected"}}
        )

        return RedirectResponse("/admin/requests", status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting request {req_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reject request: {str(e)}")
