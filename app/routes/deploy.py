import yaml
from fastapi import APIRouter, Request, Depends, HTTPException
from kubernetes.utils import create_from_yaml
from app.auth.rbac import require_role
from app.k8s.loader import get_k8s_config

router = APIRouter(prefix="/api/resources")


@router.post("/deploy")
def deploy_yaml(
    payload: dict,
    request: Request,
    user=Depends(require_role(["admin", "edit"]))
):
    """Deploy YAML to active cluster."""
    yaml_text = payload.get("yaml", "")
    if not yaml_text:
        raise HTTPException(status_code=400, detail="yaml content is required")

    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(status_code=400, detail="No active cluster selected")

    try:
        # Get kubeconfig from cluster_id
        from app.db import clusters
        from bson import ObjectId

        doc = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Cluster not found")

        kubeconfig_path = doc.get("kubeconfig_path")
        k8s_config = get_k8s_config(kubeconfig_path)
        api_client = k8s_config["api_client"]

        # Parse and deploy YAML documents
        docs = yaml.safe_load_all(yaml_text)
        deployed_objects = []
        for doc in docs:
            if doc:  # Skip empty documents
                created_obj = create_from_yaml(api_client, yaml_objects=[doc])
                deployed_objects.append(created_obj)

        return {
            "status": "success",
            "message": f"Deployed {len(deployed_objects)} objects",
            "objects": deployed_objects
        }
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")
