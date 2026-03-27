from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from kubernetes import client
from kubernetes.client import ApiClient
from kubernetes.client.rest import ApiException
from bson import ObjectId
import yaml
import json
import logging

from app.auth.session import get_current_user
from app.auth.rbac import require_role
from app.db import clusters
from app.db import audit_logs
from app.k8s.loader import load_k8s_client
from datetime import datetime

ui_router = APIRouter()
api_router = APIRouter(prefix="/api/resources/deployments")
templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)


def get_context(request):
    # Allow explicit overrides via query params (useful for API calls)
    cluster_id = request.query_params.get("cluster") or request.session.get(
        "active_cluster"
    )
    namespace = request.query_params.get("namespace") or request.session.get(
        "active_namespace"
    )

    if not cluster_id or not namespace:
        raise HTTPException(400, "Cluster and namespace required")

    # Lookup cluster; support either ObjectId string or raw id
    cluster = None
    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    except Exception:
        cluster = clusters.find_one({"_id": cluster_id})

    if not cluster:
        raise HTTPException(400, "Cluster not found")

    k8s = load_k8s_client(cluster.get("kubeconfig_path"))
    return k8s, namespace


@ui_router.get("/deployments", response_class=HTMLResponse)
def deployments_page(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    return templates.TemplateResponse(
        "deployments.html", {"request": request, "user": user}
    )


@api_router.get("/{name}")
def deployment_details(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()
    v1 = k8s.CoreV1Api()

    d = apps.read_namespaced_deployment(name, namespace)

    # rollout status
    status = "Healthy"
    if d.status.unavailable_replicas:
        status = "Degraded"
    elif d.status.updated_replicas != d.spec.replicas:
        status = "Progressing"

    # list pods owned by deployment
    selector = ",".join([f"{k}={v}" for k, v in d.spec.selector.match_labels.items()])
    pods = v1.list_namespaced_pod(namespace, label_selector=selector).items

    return {
        "name": d.metadata.name,
        "replicas": d.spec.replicas or 0,
        "ready": d.status.ready_replicas or 0,
        "updated": d.status.updated_replicas or 0,
        "available": d.status.available_replicas or 0,
        "strategy": d.spec.strategy.type,
        "containers": [
            {"name": c.name, "image": c.image} for c in d.spec.template.spec.containers
        ],
        "rollout_status": status,
        "pods": [
            {
                "name": p.metadata.name,
                "status": p.status.phase,
                "node": p.spec.node_name,
            }
            for p in pods
        ],
    }


@api_router.post("/{name}/scale")
def scale_deployment(
    name: str,
    body: dict,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()

    # Handle different body formats
    replicas = body.get("replicas") if isinstance(body, dict) else body
    if replicas is None:
        # Try to parse from string or use direct value
        replicas = int(body) if isinstance(body, (int, str)) else 1

    logger.info(
        f"Scaling deployment {name} in namespace {namespace} to {replicas} replicas"
    )

    apps.patch_namespaced_deployment_scale(
        name, namespace, {"spec": {"replicas": replicas}}, _preload_content=False
    )

    return {"status": "scaled", "replicas": replicas}


@api_router.post("/{name}/restart")
def restart_deployment(
    name: str, request: Request, user=Depends(require_role(["admin", "edit"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()

    apps.patch_namespaced_deployment(
        name,
        namespace,
        {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": "now"}
                    }
                }
            }
        },
    )

    return {"status": "restarted"}


@api_router.patch("/{name}/update-image")
def update_deployment_image(
    name: str,
    body: dict,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Update container image in a deployment."""
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()

    container_index = body.get("containerIndex", 0)
    new_image = body.get("image")

    if not new_image:
        raise HTTPException(status_code=400, detail="Image is required")

    logger.info(
        f"Updating deployment {name} in namespace {namespace} container {container_index} to image {new_image}"
    )

    # Get current deployment to find container spec
    deployment = apps.read_namespaced_deployment(name, namespace)

    # Build patch for container image - include ALL containers with only the changed one updated
    containers = deployment.spec.template.spec.containers
    if container_index >= len(containers):
        raise HTTPException(
            status_code=400, detail=f"Container index {container_index} out of range"
        )

    # Create new containers list with updated image
    updated_containers = []
    for i, container in enumerate(containers):
        if i == container_index:
            # Update the image for this container
            updated_containers.append({"name": container.name, "image": new_image})
        else:
            # Keep other containers as-is
            updated_containers.append(
                {"name": container.name, "image": container.image}
            )

    container_name = containers[container_index].name

    logger.info(f"Updated containers: {updated_containers}")

    patch = {"spec": {"template": {"spec": {"containers": updated_containers}}}}

    logger.info(f"Patching deployment {name} with: {patch}")
    apps.patch_namespaced_deployment(
        name, namespace, patch, field_manager="kube-compass"
    )
    logger.info(
        f"Successfully updated deployment {name} container {container_name} to image {new_image}"
    )

    return {"status": "updated", "container": container_name, "image": new_image}


@api_router.get("/{name}/yaml")
def get_deployment_yaml(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()
    # Use _preload_content=False to get raw JSON response - this preserves ALL fields
    # similar to 'kubectl get deployment <name> -o yaml'
    dep = apps.read_namespaced_deployment(
        name=name,
        namespace=namespace,
        _preload_content=False,
    )

    raw = dep.data.decode("utf-8")
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"yaml": raw, "editable": True}

    # Convert to YAML for a friendlier editor view (preserve order where possible)
    yaml_text = yaml.safe_dump(parsed, sort_keys=False, default_flow_style=False)

    return {"yaml": yaml_text, "editable": True}


@api_router.put("/{name}/yaml")
async def apply_deployment_yaml(
    name: str, request: Request, user=Depends(require_role(["admin", "edit"]))
):
    # Parse request early to allow cluster/namespace overrides in payload
    wrapper = await request.json()

    # Allow client to provide cluster and namespace in the JSON wrapper
    cluster_id = (
        wrapper.get("cluster")
        or request.query_params.get("cluster")
        or request.session.get("active_cluster")
    )
    namespace = (
        wrapper.get("namespace")
        or request.query_params.get("namespace")
        or request.session.get("active_namespace")
    )

    if not cluster_id or not namespace:
        raise HTTPException(400, "Cluster and namespace required")

    # Find cluster record
    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    except Exception:
        cluster = clusters.find_one({"_id": cluster_id})

    if not cluster:
        raise HTTPException(400, "Cluster not found")

    k8s = load_k8s_client(cluster.get("kubeconfig_path"))

    real_yaml = wrapper.get("yaml")
    if not real_yaml:
        raise HTTPException(400, "Empty YAML")

    # Parse YAML to validate and extract metadata for safety checks
    try:
        parsed = yaml.safe_load(real_yaml)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"Invalid YAML: {e}")

    if not isinstance(parsed, dict):
        raise HTTPException(
            400, "YAML must be a mapping/object representing a Kubernetes resource"
        )

    kind = parsed.get("kind")
    meta = parsed.get("metadata", {}) or {}
    manifest_name = meta.get("name")

    # Basic validation
    if not kind or kind.lower() != "deployment":
        raise HTTPException(400, "Provided YAML is not a Deployment")

    if manifest_name and manifest_name != name:
        raise HTTPException(400, "Resource name in YAML does not match the target name")

    # Logging the apply attempt
    user_email = user.get("email") if isinstance(user, dict) else str(user)
    dry_run = bool(wrapper.get("dry_run") or wrapper.get("dryRun"))
    logger.info(
        "User %s applying deployment %s to cluster=%s namespace=%s dry_run=%s",
        user_email,
        name,
        cluster_id,
        namespace,
        dry_run,
    )

    from kubernetes.client import ApiClient
    from kubernetes.client.rest import ApiException

    api = ApiClient()
    k8s_config = k8s  # k8s is the client module from load_k8s_client

    try:
        query_params = [
            ("fieldManager", "kubernetes-compass"),
            ("force", "true"),
        ]
        if dry_run:
            query_params.append(("dryRun", "All"))

        # Thorough cleanup of all runtime/invalid fields for server-side apply
        def clean_for_apply(obj):
            """Recursively remove runtime fields that can't be applied"""
            if not isinstance(obj, dict):
                return obj

            result = {}
            for k, v in obj.items():
                # Skip these fields entirely - they're runtime-only
                if k in (
                    "status",
                    "managedFields",
                    "resourceVersion",
                    "uid",
                    "creationTimestamp",
                    "generation",
                    "age",
                    "selfLink",
                    "creationTimestamp",
                    "deletionTimestamp",
                    "deletionGracePeriodSeconds",
                    "initializers",
                    "finalizers",
                    "clusterName",
                    "namespace",
                ):
                    continue

                if isinstance(v, dict):
                    result[k] = clean_for_apply(v)
                elif isinstance(v, list):
                    result[k] = [clean_for_apply(item) for item in v]
                else:
                    result[k] = v
            return result

        sanitized = clean_for_apply(parsed)

        # Convert sanitized manifest back to YAML text to send to the API
        real_yaml_to_apply = yaml.safe_dump(sanitized, sort_keys=False)

        # Build the full URL and use the underlying REST client's pool_manager
        # to send raw YAML bytes. This avoids ApiClient's JSON serialization.
        from urllib.parse import urlencode

        # Use the ApiClient from the loaded k8s client, not a new one
        api_client = (
            k8s_config.ApiClient() if hasattr(k8s_config, "ApiClient") else ApiClient()
        )
        base = api_client.configuration.host.rstrip("/")
        url = f"{base}/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        headers = {
            "Content-Type": "application/apply-patch+yaml",
            "Accept": "application/json",
        }

        # Pool manager request returns an HTTPResponse-like object
        resp = api_client.rest_client.pool_manager.request(
            "PATCH",
            url,
            body=real_yaml_to_apply.encode("utf-8"),
            headers=headers,
            timeout=api_client.rest_client.pool_manager.connection_pool_kw.get(
                "timeout", None
            ),
        )

        resp_bytes = resp.data if hasattr(resp, "data") else resp.read()
        resp_text = (
            resp_bytes.decode("utf-8")
            if hasattr(resp_bytes, "decode")
            else str(resp_bytes)
        )
        try:
            resp_json = yaml.safe_load(resp_text)
        except Exception:
            resp_json = None

        # Dry-run: return preview to client
        if dry_run:
            return {"dry_run": True, "preview": resp_json or resp_text}

        # Non-dry-run: record audit log and return success
        try:
            audit_logs.insert_one(
                {
                    "user": user_email,
                    "action": "apply_deployment",
                    "cluster_id": cluster_id,
                    "namespace": namespace,
                    "resource": "Deployment",
                    "name": name,
                    "manifest": parsed,
                    "timestamp": datetime.utcnow(),
                }
            )
        except Exception:
            logger.exception("Failed to write audit log")
    except ApiException as e:
        # 3. Fix the "bytes not JSON serializable" error
        # K8s error body is bytes; we must decode it to a string for FastAPI
        error_message = e.body
        if hasattr(error_message, "decode"):
            error_message = error_message.decode("utf-8")

        raise HTTPException(status_code=e.status or 500, detail=error_message)

    return {"status": "applied"}
