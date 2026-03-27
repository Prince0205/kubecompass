from fastapi import APIRouter, Request, Depends, HTTPException
from app.db import clusters
from bson import ObjectId
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from kubernetes import client as kclient
import os
import tempfile

router = APIRouter(prefix="/v1")

KUBECONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kubeconfigs"
)
os.makedirs(KUBECONFIG_DIR, exist_ok=True)


def _get_api_client_for_request(request: Request):
    cid = request.session.get("active_cluster")
    if not cid:
        raise HTTPException(status_code=400, detail="No active cluster selected")
    doc = clusters.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Cluster not found")
    kubeconfig = doc.get("kubeconfig_path")
    kclient_module = load_k8s_client(kubeconfig)
    return kclient_module


@router.get("/clusters")
def list_clusters(user=Depends(require_role(["admin", "edit", "view"]))):
    items = list(clusters.find({}, {"name": 1}))
    return [{"id": str(i["_id"]), "name": i.get("name")} for i in items]


@router.post("/clusters")
def add_cluster(payload: dict, user=Depends(require_role(["admin"]))):
    name = payload.get("name")
    kubeconfig_content = payload.get("kubeconfig_path")
    if not name or not kubeconfig_content:
        raise HTTPException(400, "name and kubeconfig_path are required")

    kubeconfig_path = os.path.join(
        KUBECONFIG_DIR, f"{name.replace(' ', '_')}_{ObjectId()}.yaml"
    )
    with open(kubeconfig_path, "w") as f:
        f.write(kubeconfig_content)

    res = clusters.insert_one({"name": name, "kubeconfig_path": kubeconfig_path})
    return {"id": str(res.inserted_id)}


@router.delete("/clusters/{cluster_id}")
def delete_cluster(cluster_id: str, user=Depends(require_role(["admin"]))):
    try:
        result = clusters.delete_one({"_id": ObjectId(cluster_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return {"success": True, "message": "Cluster deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/context")
def get_context(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    return {
        "active_cluster": request.session.get("active_cluster"),
        "active_namespace": request.session.get("active_namespace"),
    }


@router.post("/context/cluster")
def set_cluster(
    payload: dict,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    cid = payload.get("cluster_id")
    request.session["active_cluster"] = cid
    request.session.pop("active_namespace", None)
    return {"status": "ok"}


@router.post("/context/namespace")
def set_namespace(
    payload: dict,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    ns = payload.get("namespace")
    request.session["active_namespace"] = ns
    return {"status": "ok"}


@router.get("/crds")
def list_crds(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    kmod = _get_api_client_for_request(request)
    try:
        api = kmod.ApiextensionsV1Api()
        res = api.list_custom_resource_definition()
        items = []
        for i in res.items:
            items.append(
                {
                    "name": i.metadata.name,
                    "group": i.spec.group,
                    "versions": [v.name for v in i.spec.versions],
                }
            )
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage")
def list_storage(
    request: Request,
    namespace: str | None = None,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    kmod = _get_api_client_for_request(request)
    try:
        core = kmod.CoreV1Api()
        storage = kmod.StorageV1Api()
        pvs = core.list_persistent_volume().items
        if namespace:
            pvcs = core.list_namespaced_persistent_volume_claim(
                namespace=namespace
            ).items
        else:
            pvcs = core.list_persistent_volume_claim_for_all_namespaces().items
        scs = storage.list_storage_class().items
        return {
            "pv": [{"metadata": {"name": p.metadata.name}} for p in pvs],
            "pvc": [
                {
                    "metadata": {
                        "name": p.metadata.name,
                        "namespace": p.metadata.namespace,
                    }
                }
                for p in pvcs
            ],
            "sc": [{"metadata": {"name": s.metadata.name}} for s in scs],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network")
def list_network(
    request: Request,
    namespace: str | None = None,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    kmod = _get_api_client_for_request(request)
    try:
        core = kmod.CoreV1Api()
        net = kmod.NetworkingV1Api()
        if namespace:
            services = core.list_namespaced_service(namespace=namespace).items
            try:
                ingresses = net.list_namespaced_ingress(namespace=namespace).items
            except Exception:
                ingresses = []
            try:
                nps = net.list_namespaced_network_policy(namespace=namespace).items
            except Exception:
                nps = []
        else:
            services = core.list_service_for_all_namespaces().items
            ingresses = net.list_ingress_for_all_namespaces().items
            nps = net.list_network_policy_for_all_namespaces().items
        return {
            "services": [
                {"metadata": {"name": s.metadata.name}, "spec": {"type": s.spec.type}}
                for s in services
            ],
            "ingresses": [{"metadata": {"name": i.metadata.name}} for i in ingresses],
            "networkpolicies": [{"metadata": {"name": n.metadata.name}} for n in nps],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rbac")
def list_rbac(
    request: Request,
    namespace: str | None = None,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    kmod = _get_api_client_for_request(request)

    # Get namespace from session if not provided
    session_namespace = request.session.get("active_namespace", "default")

    try:
        rbac = kmod.RbacAuthorizationV1Api()

        # Handle all namespaces mode
        if session_namespace == "_all_" or session_namespace == "_all":
            roles = rbac.list_role_for_all_namespaces().items
            rolebindings = rbac.list_role_binding_for_all_namespaces().items
        elif namespace:
            roles = rbac.list_namespaced_role(namespace=namespace).items
            rolebindings = rbac.list_namespaced_role_binding(namespace=namespace).items
        else:
            roles = rbac.list_namespaced_role(namespace=session_namespace).items
            rolebindings = rbac.list_namespaced_role_binding(
                namespace=session_namespace
            ).items

        clusterroles = rbac.list_cluster_role().items
        crb = rbac.list_cluster_role_binding().items

        def serialize_role_ref(role_ref):
            if not role_ref:
                return {"apiGroup": None, "kind": None, "name": None}
            return {
                "apiGroup": role_ref.api_group,
                "kind": role_ref.kind,
                "name": role_ref.name,
            }

        def serialize_subject(subject):
            if not subject:
                return {"kind": None, "name": None, "namespace": None}
            return {
                "kind": subject.kind,
                "name": subject.name,
                "namespace": getattr(subject, "namespace", None),
            }

        bindings = [
            {
                "metadata": {
                    "name": b.metadata.name,
                    "namespace": getattr(b.metadata, "namespace", None),
                },
                "roleRef": serialize_role_ref(b.role_ref),
                "subjects": [serialize_subject(s) for s in (b.subjects or [])],
            }
            for b in rolebindings
        ]

        clusterrolebindings = [
            {
                "metadata": {"name": b.metadata.name},
                "roleRef": serialize_role_ref(b.role_ref),
                "subjects": [serialize_subject(s) for s in (b.subjects or [])],
            }
            for b in crb
        ]

        def serialize_rbac(obj):
            return {
                "apiVersion": obj.api_version,
                "kind": obj.kind,
                "metadata": {
                    "name": obj.metadata.name,
                    "namespace": getattr(obj.metadata, "namespace", None),
                    "uid": str(obj.metadata.uid),
                    "labels": obj.metadata.labels or {},
                    "annotations": obj.metadata.annotations or {},
                    "creationTimestamp": obj.metadata.creation_timestamp.isoformat()
                    if obj.metadata.creation_timestamp
                    else None,
                },
            }

        def serialize_role(obj):
            result = serialize_rbac(obj)
            result["rules"] = [
                {
                    "apiGroups": list(r.api_groups or []),
                    "resources": list(r.resources or []),
                    "verbs": list(r.verbs or []),
                    "nonResourceURLs": list(r.non_resource_urls or [])
                    if hasattr(r, "non_resource_urls")
                    else [],
                    "resourceNames": list(r.resource_names or [])
                    if hasattr(r, "resource_names")
                    else [],
                }
                for r in (obj.rules or [])
            ]
            return result

        return {
            "roles": [serialize_role(r) for r in roles],
            "clusterroles": [serialize_role(cr) for cr in clusterroles],
            "bindings": bindings,
            "clusterrolebindings": [
                {
                    "metadata": {"name": b.metadata.name},
                    "roleRef": serialize_role_ref(b.role_ref),
                    "subjects": [serialize_subject(s) for s in (b.subjects or [])],
                }
                for b in crb
            ],
        }
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Error fetching RBAC: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces")
def list_namespaces(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    kmod = _get_api_client_for_request(request)
    try:
        core = kmod.CoreV1Api()
        ns = core.list_namespace().items
        return [{"name": n.metadata.name} for n in ns]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces/{namespace_name}")
def get_namespace_details(
    namespace_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    kmod = _get_api_client_for_request(request)
    try:
        core = kmod.CoreV1Api()
        ns = core.read_namespace(namespace_name)

        return {
            "name": ns.metadata.name,
            "status": ns.status.phase if ns.status else "Active",
            "labels": ns.metadata.labels or {},
            "annotations": ns.metadata.annotations or {},
            "creation_timestamp": ns.metadata.creation_timestamp.isoformat()
            if ns.metadata.creation_timestamp
            else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/namespaces/{namespace_name}/events")
def get_namespace_events(
    namespace_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    kmod = _get_api_client_for_request(request)
    try:
        core = kmod.CoreV1Api()
        events = core.list_namespaced_event(namespace_name).items

        return [
            {
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "involved_object": e.involved_object.name
                if e.involved_object
                else None,
                "involved_object_kind": e.involved_object.kind
                if e.involved_object
                else None,
                "first_timestamp": e.first_timestamp.isoformat()
                if e.first_timestamp
                else None,
                "last_timestamp": e.last_timestamp.isoformat()
                if e.last_timestamp
                else None,
                "count": e.count or 1,
            }
            for e in events
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/namespaces")
def create_namespace(
    request: Request, payload: dict, user=Depends(require_role(["admin"]))
):
    kmod = _get_api_client_for_request(request)
    try:
        namespace_name = payload.get("name")
        if not namespace_name:
            raise HTTPException(status_code=400, detail="Namespace name is required")

        core = kmod.CoreV1Api()
        from kubernetes.client import V1Namespace, V1ObjectMeta

        namespace = V1Namespace(metadata=V1ObjectMeta(name=namespace_name))

        core.create_namespace(namespace)
        return {"success": True, "name": namespace_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resources/{resource_type}/{name}/apply")
def apply_resource_yaml(
    resource_type: str,
    name: str,
    request: Request,
    payload: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Apply YAML changes to a resource."""
    kmod = _get_api_client_for_request(request)
    namespace = request.session.get("active_namespace", "default")

    import yaml

    yaml_content = payload.get("yaml")
    if not yaml_content:
        raise HTTPException(status_code=400, detail="YAML content is required")

    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    # Thorough cleanup of all runtime/invalid fields for server-side apply
    def clean_for_apply(obj, path=""):
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

    data = clean_for_apply(data)

    try:
        import logging
        import urllib.parse
        from kubernetes.client.rest import ApiException
        from urllib.parse import urlencode

        logger = logging.getLogger(__name__)

        core = kmod.CoreV1Api()
        apps = kmod.AppsV1Api()

        # Get the API client - needed for all resource types
        api_client = kmod.ApiClient()
        base = api_client.configuration.host.rstrip("/")
        if not base or "localhost" in base.lower():
            raise HTTPException(
                status_code=500,
                detail=f"Invalid API host: {base}. Check kubeconfig.",
            )

        # Convert data back to YAML for server-side apply
        yaml_content = yaml.safe_dump(data, sort_keys=False)
        logger.info(f"Applying YAML for {resource_type}/{name}: {yaml_content[:500]}")

        if resource_type == "deployments" or resource_type == "statefulsets":
            # Use server-side apply via raw HTTP - only way to reliably persist changes
            import urllib.parse

            if resource_type == "deployments":
                url = f"{base}/apis/apps/v1/namespaces/{namespace}/deployments/{name}"
            else:
                url = f"{base}/apis/apps/v1/namespaces/{namespace}/statefulsets/{name}"

            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"

            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }

            logger.info(f"Applying YAML to {url}")
            logger.info(f"YAML content: {yaml_content[:1000]}")

            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )

            # Check response status
            resp_status = resp.status if hasattr(resp, "status") else 200
            if resp_status >= 400:
                resp_data = resp.data if hasattr(resp, "data") else b""
                raise HTTPException(
                    status_code=resp_status,
                    detail=f"API returned error {resp_status}: {resp_data.decode('utf-8', errors='replace')}",
                )

            logger.info(f"Successfully applied {resource_type} {name}")
        elif resource_type == "configmaps":
            # Use server-side apply for configmaps
            url = f"{base}/api/v1/namespaces/{namespace}/configmaps/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "secrets":
            # Use server-side apply for secrets
            url = f"{base}/api/v1/namespaces/{namespace}/secrets/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "services":
            # Use server-side apply for services
            url = f"{base}/api/v1/namespaces/{namespace}/services/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "pods":
            # Use server-side apply for pods
            url = f"{base}/api/v1/namespaces/{namespace}/pods/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "replicasets":
            # Use server-side apply for replicasets
            url = f"{base}/apis/apps/v1/namespaces/{namespace}/replicasets/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "jobs":
            # Use server-side apply for jobs
            url = f"{base}/apis/batch/v1/namespaces/{namespace}/jobs/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            batch = kmod.BatchV1Api()
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "cronjobs":
            # Use server-side apply for cronjobs
            url = f"{base}/apis/batch/v1/namespaces/{namespace}/cronjobs/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "ingresses":
            # Use server-side apply for ingresses
            url = f"{base}/apis/networking.k8s.io/v1/namespaces/{namespace}/ingresses/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "pvcs":
            # Use server-side apply for pvcs
            url = f"{base}/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "pvs":
            # Use server-side apply for persistent volumes
            url = f"{base}/api/v1/persistentvolumes/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "daemonsets":
            # Use server-side apply for daemonsets
            url = f"{base}/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "serviceaccounts":
            # Use server-side apply for service accounts
            url = f"{base}/api/v1/namespaces/{namespace}/serviceaccounts/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "roles":
            # Use server-side apply for roles
            url = f"{base}/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/roles/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "clusterroles":
            # Use server-side apply for cluster roles
            url = f"{base}/apis/rbac.authorization.k8s.io/v1/clusterroles/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "rolebindings":
            # Use server-side apply for role bindings
            url = f"{base}/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/rolebindings/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        elif resource_type == "clusterrolebindings":
            # Use server-side apply for cluster role bindings
            url = f"{base}/apis/rbac.authorization.k8s.io/v1/clusterrolebindings/{name}"
            url = f"{url}?{urllib.parse.urlencode([('fieldManager', 'kube-compass'), ('force', 'true')])}"
            headers = {
                "Content-Type": "application/apply-patch+yaml",
                "Accept": "application/json",
            }
            resp = api_client.rest_client.pool_manager.request(
                "PATCH",
                url,
                body=yaml_content.encode("utf-8"),
                headers=headers,
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported resource type: {resource_type}"
            )

        return {"status": "applied", "name": name, "type": resource_type}
    except ApiException as e:
        error_body = e.body
        if hasattr(error_body, "decode"):
            error_body = error_body.decode("utf-8")
        logger.error(f"API error applying {resource_type}/{name}: {error_body}")
        raise HTTPException(status_code=e.status or 500, detail=error_body)
    except Exception as e:
        logger.error(f"Error applying {resource_type}/{name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
