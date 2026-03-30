"""
Workload Resource Routes

Provides REST API endpoints for Kubernetes workload resources:
- Pods
- Deployments
- ReplicaSets
- StatefulSets
- DaemonSets
- Jobs
- CronJobs

Endpoints follow RESTful conventions with cluster/namespace context from session.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging

router = APIRouter(prefix="/api/resources/workload")
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


def list_resources_all_or_namespaced(k8s, namespace, list_func, *args, **kwargs):
    """Helper to list resources across all namespaces or a specific namespace."""
    if namespace == "_all_" or namespace == "_all":
        return list_func(*args, **kwargs).items
    else:
        return list_func(namespace, *args, **kwargs).items


# =============================================================================
# POD ENDPOINTS
# =============================================================================


@router.get("/pods")
def list_pods(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    """
    List all pods in active namespace.

    Returns:
      [
        {
          "name": "pod-abc123",
          "namespace": "default",
          "status": "Running",
          "node": "node1",
          "restarts": 0,
          "age": "2 days",
          "containers": 1,
          "images": ["image:latest"]
        },
        ...
      ]
    """
    try:
        k8s, namespace = get_k8s_context(request)
        v1 = k8s.CoreV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            pods = v1.list_pod_for_all_namespaces().items
        else:
            pods = v1.list_namespaced_pod(namespace).items

        result = []
        for pod in pods:
            restarts = sum(
                cs.restart_count for cs in (pod.status.container_statuses or [])
            )

            # Determine effective status from container states
            effective_status = pod.status.phase
            container_issues = []

            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.waiting:
                    reason = cs.state.waiting.reason or ""
                    if reason in (
                        "CrashLoopBackOff",
                        "ImagePullBackOff",
                        "ErrImagePull",
                        "CreateContainerConfigError",
                        "CreateContainerError",
                        "RunContainerError",
                        "InvalidImageName",
                    ):
                        container_issues.append(reason)
                elif cs.state and cs.state.terminated:
                    reason = cs.state.terminated.reason or ""
                    if reason in ("Error", "OOMKilled", "ContainerCannotRun"):
                        container_issues.append(reason)

            if container_issues:
                effective_status = container_issues[0]

            result.append(
                {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace or namespace,
                    "status": effective_status,
                    "node": pod.spec.node_name or "Unscheduled",
                    "restarts": restarts,
                    "containers": len(pod.spec.containers),
                    "images": [c.image for c in pod.spec.containers],
                    "pod_ip": pod.status.pod_ip,
                    "age": pod.metadata.creation_timestamp,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing pods: {e}")
        raise HTTPException(500, f"Failed to list pods: {str(e)}")


@router.get("/pods/{pod_name}")
def get_pod_detail(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a specific pod."""
    try:
        k8s, namespace = get_k8s_context(request)
        v1 = k8s.CoreV1Api()

        pod = v1.read_namespaced_pod(pod_name, namespace)

        return {
            "kind": "Pod",
            "apiVersion": "v1",
            "metadata": {
                "name": pod.metadata.name,
                "namespace": namespace,
                "labels": pod.metadata.labels or {},
                "annotations": pod.metadata.annotations or {},
                "uid": str(pod.metadata.uid) if pod.metadata.uid else None,
                "creationTimestamp": pod.metadata.creation_timestamp.isoformat()
                if pod.metadata.creation_timestamp
                else None,
            },
            "status": {
                "phase": pod.status.phase,
                "podIP": pod.status.pod_ip,
                "hostIP": pod.status.host_ip,
                "startTime": pod.status.start_time.isoformat()
                if pod.status.start_time
                else None,
                "qosClass": pod.status.qos_class,
            },
            "spec": {
                "nodeName": pod.spec.node_name,
                "containers": [
                    {
                        "name": c.name,
                        "image": c.image,
                        "restart_count": cs.restart_count
                        if (
                            cs := next(
                                (
                                    s
                                    for s in (pod.status.container_statuses or [])
                                    if s.name == c.name
                                ),
                                None,
                            )
                        )
                        else 0,
                    }
                    for c in pod.spec.containers
                ],
            },
            "age": str(pod.metadata.creation_timestamp)
            if pod.metadata.creation_timestamp
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pod detail: {e}")
        raise HTTPException(500, f"Failed to get pod: {str(e)}")


@router.get("/pods/{pod_name}/logs")
def get_pod_logs(
    pod_name: str,
    request: Request,
    container: str = Query(None),
    tail_lines: int = Query(200),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get logs from a pod."""
    try:
        k8s, namespace = get_k8s_context(request)
        v1 = k8s.CoreV1Api()

        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
        )

        return {"logs": logs}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pod logs: {e}")
        raise HTTPException(500, f"Failed to get logs: {str(e)}")


@router.delete("/pods/{pod_name}")
def delete_pod(
    pod_name: str, request: Request, user=Depends(require_role(["admin", "edit"]))
):
    """Delete a pod."""
    try:
        k8s, namespace = get_k8s_context(request)
        v1 = k8s.CoreV1Api()

        # Snapshot before delete
        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(k8s, "pods", pod_name, namespace)

        v1.delete_namespaced_pod(pod_name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="pods",
            resource_name=pod_name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": pod_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting pod: {e}")
        raise HTTPException(500, f"Failed to delete pod: {str(e)}")


# =============================================================================
# DEPLOYMENT ENDPOINTS
# =============================================================================


@router.get("/deployments")
def list_deployments(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all deployments in active namespace."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            deployments = apps.list_deployment_for_all_namespaces().items
        else:
            deployments = apps.list_namespaced_deployment(namespace).items

        result = []
        for dep in deployments:
            result.append(
                {
                    "name": dep.metadata.name,
                    "namespace": namespace,
                    "replicas": dep.spec.replicas or 0,
                    "ready": dep.status.ready_replicas or 0,
                    "updated": dep.status.updated_replicas or 0,
                    "available": dep.status.available_replicas or 0,
                    "age": dep.metadata.creation_timestamp,
                    "images": [c.image for c in dep.spec.template.spec.containers],
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing deployments: {e}")
        raise HTTPException(500, f"Failed to list deployments: {str(e)}")


@router.get("/deployments/{deployment_name}")
def get_deployment_detail(
    deployment_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a deployment."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        dep = apps.read_namespaced_deployment(deployment_name, namespace)

        def serialize_selector(selector):
            if not selector:
                return {}
            result = {}
            if hasattr(selector, "match_labels") and selector.match_labels:
                result["matchLabels"] = selector.match_labels
            if hasattr(selector, "match_expressions") and selector.match_expressions:
                result["matchExpressions"] = [
                    {
                        "key": e.key,
                        "operator": e.operator,
                        "values": list(e.values or []),
                    }
                    for e in selector.match_expressions
                ]
            return result

        def serialize_pod_spec(pod_spec):
            if not pod_spec:
                return {}
            containers = []
            for c in pod_spec.containers or []:
                container = {"name": c.name, "image": c.image}
                if c.env:
                    container["env"] = [
                        {"name": e.name, "value": e.value} for e in c.env
                    ]
                if c.resources:
                    container["resources"] = {
                        "limits": dict(c.resources.limits)
                        if c.resources.limits
                        else {},
                        "requests": dict(c.resources.requests)
                        if c.resources.requests
                        else {},
                    }
                containers.append(container)
            return {
                "containers": containers,
                "nodeSelector": dict(pod_spec.node_selector)
                if pod_spec.node_selector
                else {},
            }

        return {
            "kind": "Deployment",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": dep.metadata.name,
                "namespace": namespace,
                "labels": dep.metadata.labels or {},
                "annotations": dep.metadata.annotations or {},
                "uid": str(dep.metadata.uid) if dep.metadata.uid else None,
                "creationTimestamp": dep.metadata.creation_timestamp.isoformat()
                if dep.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "replicas": dep.spec.replicas or 0,
                "selector": serialize_selector(dep.spec.selector),
                "template": serialize_pod_spec(dep.spec.template.spec)
                if dep.spec.template
                else {},
                "strategy": {
                    "type": dep.spec.strategy.type
                    if dep.spec.strategy
                    else "RollingUpdate"
                }
                if dep.spec.strategy
                else {"type": "RollingUpdate"},
                "minReadySeconds": dep.spec.min_ready_seconds or 0,
                "revisionHistoryLimit": dep.spec.revision_history_limit or 10,
            },
            "status": {
                "replicas": dep.status.replicas or 0,
                "readyReplicas": dep.status.ready_replicas or 0,
                "updatedReplicas": dep.status.updated_replicas or 0,
                "availableReplicas": dep.status.available_replicas or 0,
                "conditions": [
                    {
                        "type": c.type,
                        "status": c.status,
                        "reason": c.reason,
                        "message": c.message,
                    }
                    for c in (dep.status.conditions or [])
                ]
                if dep.status.conditions
                else [],
            },
            "age": str(dep.metadata.creation_timestamp)
            if dep.metadata.creation_timestamp
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deployment detail: {e}")
        raise HTTPException(500, f"Failed to get deployment: {str(e)}")


@router.patch("/deployments/{deployment_name}/scale")
def scale_deployment(
    deployment_name: str,
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Scale deployment to specified number of replicas."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        replicas = body.get("replicas") if body else None
        if replicas is None:
            raise HTTPException(400, "replicas is required")

        # Snapshot before scale
        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(
            k8s, "deployments", deployment_name, namespace
        )

        body = {"spec": {"replicas": replicas}}
        result = apps.patch_namespaced_deployment(deployment_name, namespace, body)

        yaml_after = _fetch_resource_yaml(
            k8s, "deployments", deployment_name, namespace
        )
        save_resource_snapshot(
            request=request,
            resource_type="deployments",
            resource_name=deployment_name,
            operation="scale",
            user_email=user_email,
            yaml_before=yaml_before,
            yaml_after=yaml_after,
        )

        return {
            "status": "scaled",
            "name": deployment_name,
            "replicas": result.spec.replicas,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scaling deployment: {e}")
        raise HTTPException(500, f"Failed to scale deployment: {str(e)}")


@router.patch("/deployments/{deployment_name}/update-image")
def update_deployment_image(
    deployment_name: str,
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Update container image in a deployment."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        container_index = body.get("containerIndex", 0)
        new_image = body.get("image")

        if not new_image:
            raise HTTPException(status_code=400, detail="Image is required")

        logger.info(
            f"Updating deployment {deployment_name} in namespace {namespace} container {container_index} to image {new_image}"
        )

        # Snapshot before update
        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(
            k8s, "deployments", deployment_name, namespace
        )

        deployment = apps.read_namespaced_deployment(deployment_name, namespace)

        containers = deployment.spec.template.spec.containers
        if container_index >= len(containers):
            raise HTTPException(
                status_code=400,
                detail=f"Container index {container_index} out of range",
            )

        container_name = containers[container_index].name

        updated_containers = []
        for i, container in enumerate(containers):
            if i == container_index:
                updated_containers.append({"name": container.name, "image": new_image})
            else:
                updated_containers.append(
                    {"name": container.name, "image": container.image}
                )

        patch = {"spec": {"template": {"spec": {"containers": updated_containers}}}}

        apps.patch_namespaced_deployment(
            deployment_name, namespace, patch, field_manager="kube-compass"
        )

        logger.info(
            f"Successfully updated deployment {deployment_name} container {container_name} to image {new_image}"
        )

        yaml_after = _fetch_resource_yaml(
            k8s, "deployments", deployment_name, namespace
        )
        save_resource_snapshot(
            request=request,
            resource_type="deployments",
            resource_name=deployment_name,
            operation="update-image",
            user_email=user_email,
            yaml_before=yaml_before,
            yaml_after=yaml_after,
        )

        return {"status": "updated", "container": container_name, "image": new_image}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating deployment image: {e}")
        raise HTTPException(500, f"Failed to update deployment image: {str(e)}")


@router.delete("/deployments/{deployment_name}")
def delete_deployment(
    deployment_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Delete a deployment."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(
            k8s, "deployments", deployment_name, namespace
        )

        apps.delete_namespaced_deployment(deployment_name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="deployments",
            resource_name=deployment_name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": deployment_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deployment: {e}")
        raise HTTPException(500, f"Failed to delete deployment: {str(e)}")


# =============================================================================
# REPLICASET ENDPOINTS
# =============================================================================


@router.get("/replicasets")
def list_replicasets(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all replicasets in active namespace."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            rss = apps.list_replica_set_for_all_namespaces().items
        else:
            rss = apps.list_namespaced_replica_set(namespace).items

        result = []
        for rs in rss:
            result.append(
                {
                    "name": rs.metadata.name,
                    "namespace": namespace,
                    "desired": rs.spec.replicas or 0,
                    "ready": rs.status.ready_replicas or 0,
                    "available": rs.status.available_replicas or 0,
                    "age": rs.metadata.creation_timestamp,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing replicasets: {e}")
        raise HTTPException(500, f"Failed to list replicasets: {str(e)}")


@router.get("/replicasets/{replicaset_name}")
def get_replicaset_detail(
    replicaset_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a replicaset."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        rs = apps.read_namespaced_replica_set(replicaset_name, namespace)

        def serialize_selector(selector):
            if not selector:
                return {}
            result = {}
            if hasattr(selector, "match_labels") and selector.match_labels:
                result["matchLabels"] = selector.match_labels
            if hasattr(selector, "match_expressions") and selector.match_expressions:
                result["matchExpressions"] = [
                    {
                        "key": e.key,
                        "operator": e.operator,
                        "values": list(e.values or []),
                    }
                    for e in selector.match_expressions
                ]
            return result

        return {
            "kind": "ReplicaSet",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": rs.metadata.name,
                "namespace": namespace,
                "labels": rs.metadata.labels or {},
                "annotations": rs.metadata.annotations or {},
                "uid": str(rs.metadata.uid) if rs.metadata.uid else None,
                "creationTimestamp": rs.metadata.creation_timestamp.isoformat()
                if rs.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "replicas": rs.spec.replicas or 0,
                "selector": serialize_selector(rs.spec.selector),
            },
            "status": {
                "replicas": rs.status.replicas or 0,
                "readyReplicas": rs.status.ready_replicas or 0,
                "availableReplicas": rs.status.available_replicas or 0,
            },
            "age": str(rs.metadata.creation_timestamp)
            if rs.metadata.creation_timestamp
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting replicaset detail: {e}")
        raise HTTPException(500, f"Failed to get replicaset: {str(e)}")


# =============================================================================
# STATEFULSET ENDPOINTS
# =============================================================================


@router.get("/statefulsets")
def list_statefulsets(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all statefulsets in active namespace."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            sts_list = apps.list_stateful_set_for_all_namespaces().items
        else:
            sts_list = apps.list_namespaced_stateful_set(namespace).items

        result = []
        for sts in sts_list:
            result.append(
                {
                    "name": sts.metadata.name,
                    "namespace": namespace,
                    "replicas": sts.spec.replicas or 0,
                    "ready": sts.status.ready_replicas or 0,
                    "service": sts.spec.service_name,
                    "age": sts.metadata.creation_timestamp,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing statefulsets: {e}")
        raise HTTPException(500, f"Failed to list statefulsets: {str(e)}")


@router.get("/statefulsets/{statefulset_name}")
def get_statefulset_detail(
    statefulset_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a statefulset."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        sts = apps.read_namespaced_stateful_set(statefulset_name, namespace)

        return {
            "kind": "StatefulSet",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": sts.metadata.name,
                "namespace": namespace,
                "labels": sts.metadata.labels or {},
                "annotations": sts.metadata.annotations or {},
                "uid": str(sts.metadata.uid) if sts.metadata.uid else None,
                "creationTimestamp": sts.metadata.creation_timestamp.isoformat()
                if sts.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "replicas": sts.spec.replicas or 0,
                "serviceName": sts.spec.service_name or "",
                "selector": {"matchLabels": sts.spec.selector.match_labels}
                if sts.spec.selector and sts.spec.selector.match_labels
                else {},
                "updateStrategy": {
                    "type": sts.spec.update_strategy.type
                    if sts.spec.update_strategy
                    else "RollingUpdate"
                },
                "podManagementPolicy": sts.spec.pod_management_policy or "OrderedReady",
            },
            "status": {
                "replicas": sts.status.replicas or 0,
                "readyReplicas": sts.status.ready_replicas or 0,
                "currentReplicas": sts.status.current_replicas or 0,
                "updatedReplicas": sts.status.updated_replicas or 0,
                "conditions": [
                    {"type": c.type, "status": c.status, "reason": c.reason}
                    for c in (sts.status.conditions or [])
                ]
                if sts.status.conditions
                else [],
            },
            "age": str(sts.metadata.creation_timestamp)
            if sts.metadata.creation_timestamp
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting statefulset detail: {e}")
        raise HTTPException(500, f"Failed to get statefulset: {str(e)}")


@router.patch("/statefulsets/{statefulset_name}/scale")
def scale_statefulset(
    statefulset_name: str,
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Scale statefulset to specified number of replicas."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        replicas = body.get("replicas") if body else None
        if replicas is None:
            raise HTTPException(400, "replicas is required")

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(
            k8s, "statefulsets", statefulset_name, namespace
        )

        body = {"spec": {"replicas": replicas}}
        result = apps.patch_namespaced_stateful_set(statefulset_name, namespace, body)

        yaml_after = _fetch_resource_yaml(
            k8s, "statefulsets", statefulset_name, namespace
        )
        save_resource_snapshot(
            request=request,
            resource_type="statefulsets",
            resource_name=statefulset_name,
            operation="scale",
            user_email=user_email,
            yaml_before=yaml_before,
            yaml_after=yaml_after,
        )

        return {
            "status": "scaled",
            "name": statefulset_name,
            "replicas": result.spec.replicas,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scaling statefulset: {e}")
        raise HTTPException(500, f"Failed to scale statefulset: {str(e)}")


@router.delete("/statefulsets/{statefulset_name}")
def delete_statefulset(
    statefulset_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Delete a statefulset."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(
            k8s, "statefulsets", statefulset_name, namespace
        )

        apps.delete_namespaced_stateful_set(statefulset_name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="statefulsets",
            resource_name=statefulset_name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": statefulset_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting statefulset: {e}")
        raise HTTPException(500, f"Failed to delete statefulset: {str(e)}")


# =============================================================================
# DAEMONSET ENDPOINTS
# =============================================================================


@router.get("/daemonsets")
def list_daemonsets(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all daemonsets in active namespace."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            dss = apps.list_daemon_set_for_all_namespaces().items
        else:
            dss = apps.list_namespaced_daemon_set(namespace).items

        result = []
        for ds in dss:
            result.append(
                {
                    "name": ds.metadata.name,
                    "namespace": namespace,
                    "desired": ds.status.desired_number_scheduled or 0,
                    "ready": ds.status.number_ready or 0,
                    "available": ds.status.number_available or 0,
                    "age": ds.metadata.creation_timestamp,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing daemonsets: {e}")
        raise HTTPException(500, f"Failed to list daemonsets: {str(e)}")


@router.get("/daemonsets/{daemonset_name}")
def get_daemonset_detail(
    daemonset_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a daemonset."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        ds = apps.read_namespaced_daemon_set(daemonset_name, namespace)

        return {
            "kind": "DaemonSet",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": ds.metadata.name,
                "namespace": namespace,
                "labels": ds.metadata.labels or {},
                "annotations": ds.metadata.annotations or {},
                "uid": str(ds.metadata.uid) if ds.metadata.uid else None,
                "creationTimestamp": ds.metadata.creation_timestamp.isoformat()
                if ds.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "selector": {"matchLabels": ds.spec.selector.match_labels}
                if ds.spec.selector and ds.spec.selector.match_labels
                else {},
                "updateStrategy": {
                    "type": ds.spec.update_strategy.type
                    if ds.spec.update_strategy
                    else "RollingUpdate"
                },
                "minReadySeconds": ds.spec.min_ready_seconds or 0,
            },
            "status": {
                "desiredNumberScheduled": ds.status.desired_number_scheduled or 0,
                "currentNumberScheduled": ds.status.current_number_scheduled or 0,
                "numberReady": ds.status.number_ready or 0,
                "numberAvailable": ds.status.number_available or 0,
                "numberUnavailable": ds.status.number_unavailable or 0,
                "conditions": [
                    {"type": c.type, "status": c.status, "reason": c.reason}
                    for c in (ds.status.conditions or [])
                ]
                if ds.status.conditions
                else [],
            },
            "age": str(ds.metadata.creation_timestamp)
            if ds.metadata.creation_timestamp
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daemonset detail: {e}")
        raise HTTPException(500, f"Failed to get daemonset: {str(e)}")


@router.delete("/daemonsets/{daemonset_name}")
def delete_daemonset(
    daemonset_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Delete a daemonset."""
    try:
        k8s, namespace = get_k8s_context(request)
        apps = k8s.AppsV1Api()

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(k8s, "daemonsets", daemonset_name, namespace)

        apps.delete_namespaced_daemon_set(daemonset_name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="daemonsets",
            resource_name=daemonset_name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": daemonset_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting daemonset: {e}")
        raise HTTPException(500, f"Failed to delete daemonset: {str(e)}")


# =============================================================================
# JOB ENDPOINTS
# =============================================================================


@router.get("/jobs")
def list_jobs(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    """List all jobs in active namespace."""
    try:
        k8s, namespace = get_k8s_context(request)
        batch = k8s.BatchV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            jobs = batch.list_job_for_all_namespaces().items
        else:
            jobs = batch.list_namespaced_job(namespace).items

        result = []
        for job in jobs:
            result.append(
                {
                    "name": job.metadata.name,
                    "namespace": namespace,
                    "completions": job.spec.completions or 0,
                    "succeeded": job.status.succeeded or 0,
                    "failed": job.status.failed or 0,
                    "active": job.status.active or 0,
                    "age": job.metadata.creation_timestamp,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(500, f"Failed to list jobs: {str(e)}")


@router.get("/jobs/{job_name}")
def get_job_detail(
    job_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a job."""
    try:
        k8s, namespace = get_k8s_context(request)
        batch = k8s.BatchV1Api()

        job = batch.read_namespaced_job(job_name, namespace)

        return {
            "name": job.metadata.name,
            "namespace": namespace,
            "completions": job.spec.completions or 0,
            "succeeded": job.status.succeeded or 0,
            "failed": job.status.failed or 0,
            "active": job.status.active or 0,
            "labels": job.metadata.labels or {},
            "age": job.metadata.creation_timestamp,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job detail: {e}")
        raise HTTPException(500, f"Failed to get job: {str(e)}")


@router.delete("/jobs/{job_name}")
def delete_job(
    job_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Delete a job."""
    try:
        k8s, namespace = get_k8s_context(request)
        batch = k8s.BatchV1Api()

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(k8s, "jobs", job_name, namespace)

        batch.delete_namespaced_job(job_name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="jobs",
            resource_name=job_name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": job_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(500, f"Failed to delete job: {str(e)}")


# =============================================================================
# CRONJOB ENDPOINTS
# =============================================================================


@router.get("/cronjobs")
def list_cronjobs(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all cronjobs in active namespace."""
    try:
        k8s, namespace = get_k8s_context(request)
        batch = k8s.BatchV1Api()

        # Handle "all namespaces" mode
        if namespace == "_all_" or namespace == "_all":
            cronjobs = batch.list_cron_job_for_all_namespaces().items
        else:
            cronjobs = batch.list_namespaced_cron_job(namespace).items

        result = []
        for cj in cronjobs:
            result.append(
                {
                    "name": cj.metadata.name,
                    "namespace": namespace,
                    "schedule": cj.spec.schedule,
                    "active": len(cj.status.active or []),
                    "last_schedule": cj.status.last_schedule_time,
                    "age": cj.metadata.creation_timestamp,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing cronjobs: {e}")
        raise HTTPException(500, f"Failed to list cronjobs: {str(e)}")


@router.get("/cronjobs/{cronjob_name}")
def get_cronjob_detail(
    cronjob_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get detailed information about a cronjob."""
    try:
        k8s, namespace = get_k8s_context(request)
        batch = k8s.BatchV1Api()

        cj = batch.read_namespaced_cron_job(cronjob_name, namespace)

        return {
            "name": cj.metadata.name,
            "namespace": namespace,
            "schedule": cj.spec.schedule,
            "active": len(cj.status.active or []),
            "last_schedule": cj.status.last_schedule_time,
            "last_successful": cj.status.last_successful_time,
            "labels": cj.metadata.labels or {},
            "age": cj.metadata.creation_timestamp,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cronjob detail: {e}")
        raise HTTPException(500, f"Failed to get cronjob: {str(e)}")


@router.delete("/cronjobs/{cronjob_name}")
def delete_cronjob(
    cronjob_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Delete a cronjob."""
    try:
        k8s, namespace = get_k8s_context(request)
        batch = k8s.BatchV1Api()

        from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

        user_email = user.get("email") if isinstance(user, dict) else str(user)
        yaml_before = _fetch_resource_yaml(k8s, "cronjobs", cronjob_name, namespace)

        batch.delete_namespaced_cron_job(cronjob_name, namespace)

        save_resource_snapshot(
            request=request,
            resource_type="cronjobs",
            resource_name=cronjob_name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {"status": "deleted", "name": cronjob_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cronjob: {e}")
        raise HTTPException(500, f"Failed to delete cronjob: {str(e)}")


# =============================================================================
# End of Routes
# =============================================================================
