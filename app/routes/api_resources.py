from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import yaml
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resources")


def get_context(request):
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace")

    if not cluster_id or not namespace:
        raise HTTPException(status_code=400, detail="Cluster or namespace not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    k8s = load_k8s_client(cluster.get("kubeconfig_path"))

    return k8s, namespace


def get_cluster_context(request):
    """Get cluster context without requiring namespace."""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(status_code=400, detail="No cluster selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    k8s = load_k8s_client(cluster["kubeconfig_path"])
    return k8s


@router.post("/namespace")
def create_namespace(
    request: Request, payload: dict, user=Depends(require_role(["admin"]))
):
    """Create a new namespace in the cluster."""
    k8s = get_cluster_context(request)

    try:
        namespace_name = payload.get("name")
        if not namespace_name:
            raise HTTPException(status_code=400, detail="Namespace name is required")

        v1 = k8s.CoreV1Api()
        from kubernetes.client import V1Namespace, V1ObjectMeta

        namespace = V1Namespace(metadata=V1ObjectMeta(name=namespace_name))

        v1.create_namespace(namespace)
        return {"success": True, "name": namespace_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configmaps")
def list_configmaps(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    cms = v1.list_namespaced_config_map(namespace)

    return [
        {
            "name": cm.metadata.name,
            "data_keys": len(cm.data or {}),
            "age": cm.metadata.creation_timestamp,
            "labels": cm.metadata.labels,
        }
        for cm in cms.items
    ]


@router.get("/configmaps/{name}")
def get_configmap(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    cm = v1.read_namespaced_config_map(name, namespace)

    return {
        "metadata": {
            "name": cm.metadata.name,
            "labels": cm.metadata.labels,
            "annotations": cm.metadata.annotations,
        },
        "data": cm.data or {},
    }


@router.patch("/configmaps/{name}")
def update_configmap(
    name: str,
    body: dict,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    v1.patch_namespaced_config_map(name, namespace, {"data": body["data"]})

    return {"status": "updated"}


@router.get("/secrets")
def list_secrets(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    secrets = v1.list_namespaced_secret(namespace)

    return [
        {
            "name": s.metadata.name,
            "type": s.type,
            "keys": list(s.data.keys()) if s.data else [],
            "age": s.metadata.creation_timestamp,
        }
        for s in secrets.items
    ]


@router.get("/pods")
def list_pods(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    pods = v1.list_namespaced_pod(namespace).items

    result = []
    for p in pods:
        result.append(
            {
                "name": p.metadata.name,
                "status": p.status.phase,
                "node": p.spec.node_name,
                "restarts": sum(
                    cs.restart_count for cs in (p.status.container_statuses or [])
                ),
            }
        )

    return result


@router.get("/services")
def list_services(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    svcs = v1.list_namespaced_service(namespace)

    return [
        {"name": s.metadata.name, "type": s.spec.type, "cluster_ip": s.spec.cluster_ip}
        for s in svcs.items
    ]


@router.get("/deployments")
def list_deployments(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()

    deps = apps.list_namespaced_deployment(namespace)

    return [
        {
            "name": d.metadata.name,
            "replicas": d.spec.replicas or 0,
            "ready": d.status.ready_replicas or 0,
        }
        for d in deps.items
    ]


@router.get("/ingresses")
def list_ingresses(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    net = k8s.NetworkingV1Api()

    ing = net.list_namespaced_ingress(namespace)

    return [
        {
            "name": i.metadata.name,
            "hosts": [r.host for r in i.spec.rules] if i.spec.rules else [],
        }
        for i in ing.items
    ]


@router.get("/statefulsets")
def list_statefulsets(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()

    sts = apps.list_namespaced_stateful_set(namespace)

    return [
        {"name": s.metadata.name, "replicas": s.status.ready_replicas or 0}
        for s in sts.items
    ]


@router.get("/replicasets")
def list_replicasets(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    apps = k8s.AppsV1Api()

    rss = apps.list_namespaced_replica_set(namespace).items

    return [
        {
            "name": rs.metadata.name,
            "desired": rs.spec.replicas or 0,
            "ready": rs.status.ready_replicas or 0,
            "available": rs.status.available_replicas or 0,
            "owner": next(
                (
                    o.name
                    for o in rs.metadata.owner_references or []
                    if o.kind == "Deployment"
                ),
                None,
            ),
        }
        for rs in rss
    ]


@router.get("/pv")
def list_pvs(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    k8s, _ = get_context(request)
    v1 = k8s.CoreV1Api()
    pvs = v1.list_persistent_volume().items
    return [
        {
            "name": p.metadata.name,
            "capacity": (p.spec.capacity or {}).get("storage")
            if getattr(p, "spec", None)
            else None,
            "reclaim": getattr(p.spec, "persistent_volume_reclaim_policy", None),
        }
        for p in pvs
    ]


@router.get("/pvc")
def list_pvcs(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()
    pvcs = v1.list_namespaced_persistent_volume_claim(namespace).items
    return [
        {
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "status": getattr(p.status, "phase", None),
            "storage": (p.spec.resources.requests or {}).get("storage")
            if getattr(p, "spec", None)
            else None,
        }
        for p in pvcs
    ]


@router.get("/storageclasses")
def list_storageclasses(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, _ = get_context(request)
    try:
        storage = k8s.StorageV1Api()
        scs = storage.list_storage_class().items
    except Exception:
        scs = []
    return [
        {"name": s.metadata.name, "provisioner": getattr(s, "provisioner", None)}
        for s in scs
    ]


@router.get("/roles")
def list_roles(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    k8s, namespace = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    roles = rbac.list_namespaced_role(namespace).items
    return [{"name": r.metadata.name, "namespace": r.metadata.namespace} for r in roles]


@router.get("/rolebindings")
def list_rolebindings(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    rbs = rbac.list_namespaced_role_binding(namespace).items
    return [
        {"name": b.metadata.name, "namespace": getattr(b.metadata, "namespace", None)}
        for b in rbs
    ]


@router.get("/clusterroles")
def list_clusterroles(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, _ = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    crs = rbac.list_cluster_role().items
    return [{"name": c.metadata.name} for c in crs]


@router.get("/clusterrolebindings")
def list_clusterrolebindings(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, _ = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    crbs = rbac.list_cluster_role_binding().items
    return [{"name": b.metadata.name} for b in crbs]


@router.get("/serviceaccounts")
def list_serviceaccounts(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()
    sas = v1.list_namespaced_service_account(namespace).items
    return [{"name": s.metadata.name, "namespace": s.metadata.namespace} for s in sas]


@router.get("/endpoints")
def list_endpoints(
    request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()
    endpoints = v1.list_namespaced_endpoints(namespace).items
    return [
        {"name": e.metadata.name, "namespace": e.metadata.namespace} for e in endpoints
    ]


@router.get("/rolebindings/{name}")
def get_rolebinding_detail(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    rb = rbac.read_namespaced_role_binding(name, namespace)

    return {
        "kind": "RoleBinding",
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "metadata": {
            "name": rb.metadata.name,
            "namespace": rb.metadata.namespace,
            "uid": str(rb.metadata.uid) if rb.metadata.uid else None,
            "labels": rb.metadata.labels or {},
            "annotations": rb.metadata.annotations or {},
            "creationTimestamp": rb.metadata.creation_timestamp.isoformat()
            if rb.metadata.creation_timestamp
            else None,
        },
        "roleRef": {
            "apiGroup": rb.role_ref.api_group,
            "kind": rb.role_ref.kind,
            "name": rb.role_ref.name,
        },
        "subjects": [
            {
                "kind": s.kind,
                "name": s.name,
                "namespace": s.namespace,
                "apiGroup": s.api_group,
            }
            for s in (rb.subjects or [])
        ],
    }


@router.get("/clusterroles/{name}")
def get_clusterrole_detail(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, _ = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    cr = rbac.read_cluster_role(name)

    return {
        "kind": "ClusterRole",
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "metadata": {
            "name": cr.metadata.name,
            "uid": str(cr.metadata.uid) if cr.metadata.uid else None,
            "labels": cr.metadata.labels or {},
            "annotations": cr.metadata.annotations or {},
            "creationTimestamp": cr.metadata.creation_timestamp.isoformat()
            if cr.metadata.creation_timestamp
            else None,
        },
        "rules": [
            {
                "verbs": list(r.verbs) if r.verbs else [],
                "apiGroups": list(r.api_groups) if r.api_groups else [],
                "resources": list(r.resources) if r.resources else [],
                "resourceNames": list(r.resource_names) if r.resource_names else [],
                "nonResourceURLs": list(r.non_resource_ur_ls)
                if r.non_resource_ur_ls
                else [],
            }
            for r in (cr.rules or [])
        ],
    }


@router.get("/clusterrolebindings/{name}")
def get_clusterrolebinding_detail(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, _ = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    crb = rbac.read_cluster_role_binding(name)

    return {
        "kind": "ClusterRoleBinding",
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "metadata": {
            "name": crb.metadata.name,
            "uid": str(crb.metadata.uid) if crb.metadata.uid else None,
            "labels": crb.metadata.labels or {},
            "annotations": crb.metadata.annotations or {},
            "creationTimestamp": crb.metadata.creation_timestamp.isoformat()
            if crb.metadata.creation_timestamp
            else None,
        },
        "roleRef": {
            "apiGroup": crb.role_ref.api_group,
            "kind": crb.role_ref.kind,
            "name": crb.role_ref.name,
        },
        "subjects": [
            {
                "kind": s.kind,
                "name": s.name,
                "namespace": s.namespace,
                "apiGroup": s.api_group,
            }
            for s in (crb.subjects or [])
        ],
    }


@router.get("/roles/{name}")
def get_role_detail(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    rbac = k8s.RbacAuthorizationV1Api()
    role = rbac.read_namespaced_role(name, namespace)

    return {
        "kind": "Role",
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "metadata": {
            "name": role.metadata.name,
            "namespace": role.metadata.namespace,
            "uid": str(role.metadata.uid) if role.metadata.uid else None,
            "labels": role.metadata.labels or {},
            "annotations": role.metadata.annotations or {},
            "creationTimestamp": role.metadata.creation_timestamp.isoformat()
            if role.metadata.creation_timestamp
            else None,
        },
        "rules": [
            {
                "verbs": list(r.verbs) if r.verbs else [],
                "apiGroups": list(r.api_groups) if r.api_groups else [],
                "resources": list(r.resources) if r.resources else [],
                "resourceNames": list(r.resource_names) if r.resource_names else [],
                "nonResourceURLs": list(r.non_resource_ur_ls)
                if r.non_resource_ur_ls
                else [],
            }
            for r in (role.rules or [])
        ],
    }


@router.get("/endpoints/{name}")
def get_endpoints_detail(
    name: str, request: Request, user=Depends(require_role(["admin", "edit", "view"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()
    ep = v1.read_namespaced_endpoints(name, namespace)

    subsets_data = []
    if ep.subsets:
        for subset in ep.subsets:
            addresses = []
            if subset.addresses:
                for addr in subset.addresses:
                    addresses.append(
                        {
                            "ip": addr.ip,
                            "hostname": addr.hostname,
                            "targetRef": {
                                "kind": addr.target_ref.kind
                                if addr.target_ref
                                else None,
                                "name": addr.target_ref.name
                                if addr.target_ref
                                else None,
                                "namespace": addr.target_ref.namespace
                                if addr.target_ref
                                else None,
                            }
                            if addr.target_ref
                            else None,
                        }
                    )

            ports = []
            if subset.ports:
                for port in subset.ports:
                    ports.append(
                        {
                            "port": port.port,
                            "protocol": port.protocol or "TCP",
                            "name": port.name,
                        }
                    )

            subsets_data.append({"addresses": addresses, "ports": ports})

    return {
        "kind": "Endpoints",
        "apiVersion": "v1",
        "metadata": {
            "name": ep.metadata.name,
            "namespace": ep.metadata.namespace,
            "labels": ep.metadata.labels or {},
            "annotations": ep.metadata.annotations or {},
            "creationTimestamp": ep.metadata.creation_timestamp.isoformat()
            if ep.metadata.creation_timestamp
            else None,
        },
        "subsets": subsets_data,
    }


@router.get("/{resource}/{name}/yaml")
def get_resource_yaml(
    resource: str,
    name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get resource YAML - returns full resource definition like kubectl get -o yaml"""
    k8s, namespace = get_context(request)

    # Cluster-scoped resources don't need namespace
    cluster_scoped = {"pv", "storageclasses", "clusterroles", "clusterrolebindings"}

    # For cluster-scoped resources or when namespace is _all_, use a default namespace
    effective_namespace = namespace
    if namespace in ("_all_", "_all") or resource in cluster_scoped:
        # Get first namespace from available namespaces or use "default"
        try:
            ns_list = k8s.CoreV1Api().list_namespace().items
            if ns_list:
                effective_namespace = ns_list[0].metadata.name
            else:
                effective_namespace = "default"
        except:
            effective_namespace = "default"

    # Map resource to the appropriate read function with _preload_content=False
    # to get complete resource definition similar to kubectl get -o yaml
    api_map = {
        "deployments": lambda: k8s.AppsV1Api().read_namespaced_deployment(
            name, effective_namespace, _preload_content=False
        ),
        "replicasets": lambda: k8s.AppsV1Api().read_namespaced_replica_set(
            name, effective_namespace, _preload_content=False
        ),
        "pods": lambda: k8s.CoreV1Api().read_namespaced_pod(
            name, effective_namespace, _preload_content=False
        ),
        "configmaps": lambda: k8s.CoreV1Api().read_namespaced_config_map(
            name, effective_namespace, _preload_content=False
        ),
        "services": lambda: k8s.CoreV1Api().read_namespaced_service(
            name, effective_namespace, _preload_content=False
        ),
        "statefulsets": lambda: k8s.AppsV1Api().read_namespaced_stateful_set(
            name, effective_namespace, _preload_content=False
        ),
        "daemonsets": lambda: k8s.AppsV1Api().read_namespaced_daemon_set(
            name, effective_namespace, _preload_content=False
        ),
        "jobs": lambda: k8s.BatchV1Api().read_namespaced_job(
            name, effective_namespace, _preload_content=False
        ),
        "cronjobs": lambda: k8s.BatchV1Api().read_namespaced_cron_job(
            name, effective_namespace, _preload_content=False
        ),
        "ingresses": lambda: k8s.NetworkingV1Api().read_namespaced_ingress(
            name, effective_namespace, _preload_content=False
        ),
        "pv": lambda: k8s.CoreV1Api().read_persistent_volume(
            name, _preload_content=False
        ),
        "pvc": lambda: k8s.CoreV1Api().read_namespaced_persistent_volume_claim(
            name, namespace, _preload_content=False
        ),
        "storageclasses": lambda: k8s.StorageV1Api().read_storage_class(
            name, _preload_content=False
        ),
        "serviceaccounts": lambda: k8s.CoreV1Api().read_namespaced_service_account(
            name, effective_namespace, _preload_content=False
        ),
        "roles": lambda: k8s.RbacAuthorizationV1Api().read_namespaced_role(
            name, effective_namespace, _preload_content=False
        ),
        "rolebindings": lambda: k8s.RbacAuthorizationV1Api().read_namespaced_role_binding(
            name, effective_namespace, _preload_content=False
        ),
        "clusterroles": lambda: k8s.RbacAuthorizationV1Api().read_cluster_role(
            name, _preload_content=False
        ),
        "clusterrolebindings": lambda: k8s.RbacAuthorizationV1Api().read_cluster_role_binding(
            name, _preload_content=False
        ),
        "secrets": lambda: k8s.CoreV1Api().read_namespaced_secret(
            name, effective_namespace, _preload_content=False
        ),
        "hpas": lambda: k8s.AutoscalingV2Api().read_namespaced_horizontal_pod_autoscaler(
            name, effective_namespace, _preload_content=False
        ),
        "networkpolicies": lambda: k8s.NetworkingV1Api().read_namespaced_network_policy(
            name, effective_namespace, _preload_content=False
        ),
        "endpoints": lambda: k8s.CoreV1Api().read_namespaced_endpoints(
            name, effective_namespace, _preload_content=False
        ),
        "limitranges": lambda: k8s.CoreV1Api().read_namespaced_limit_range(
            name, effective_namespace, _preload_content=False
        ),
        "resourcequotas": lambda: k8s.CoreV1Api().read_namespaced_resource_quota(
            name, effective_namespace, _preload_content=False
        ),
    }

    if resource not in api_map:
        raise HTTPException(
            status_code=400, detail=f"Unsupported resource type: {resource}"
        )

    try:
        obj = api_map[resource]()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Parse the raw response and convert to YAML
    raw = obj.data.decode("utf-8")
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = raw

    if isinstance(parsed, dict):
        yaml_text = yaml.safe_dump(parsed, sort_keys=False, default_flow_style=False)
    else:
        yaml_text = str(parsed)

    return {"yaml": yaml_text}


@router.put("/{resource}/{name}/yaml")
async def apply_resource_yaml(
    resource: str,
    name: str,
    request: Request,
    body: dict = Body(...),
    user=Depends(require_role(["admin", "edit"])),
):
    """Apply (replace) a resource YAML using server-side apply like kubectl apply/edit.

    This uses the server-side apply mechanism which is similar to 'kubectl apply' or 'kubectl edit'.
    It properly handles all fields including image tags, env vars, volume mounts, probes, etc.

    Expects JSON body: {"yaml": "...", "dry_run": false}
    """
    k8s, namespace = get_context(request)
    dry_run = body.get("dry_run", False)

    if "yaml" not in body:
        raise HTTPException(status_code=400, detail="Missing 'yaml' in request body")

    # Capture snapshot before apply for history
    from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

    user_email = user.get("email") if isinstance(user, dict) else str(user)
    yaml_before = (
        _fetch_resource_yaml(k8s, resource, name, namespace) if not dry_run else None
    )

    try:
        parsed = yaml.safe_load(body["yaml"])
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    if not isinstance(parsed, dict):
        raise HTTPException(
            400, "YAML must be a mapping/object representing a Kubernetes resource"
        )

    # Validate resource name matches
    meta = parsed.get("metadata", {}) or {}
    manifest_name = meta.get("name")
    if manifest_name and manifest_name != name:
        raise HTTPException(400, "Resource name in YAML does not match the URL")

    # cluster-scoped resources should only be mutated by admins
    cluster_scoped = {"pv", "storageclasses", "clusterroles", "clusterrolebindings"}
    if resource in cluster_scoped and user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin role required to modify cluster-scoped resources",
        )

    # Clean up runtime fields that can't be applied
    def clean_for_apply(obj):
        """Remove runtime-only fields that shouldn't be sent in apply"""
        if not isinstance(obj, dict):
            return obj
        result = {}
        runtime_fields = {
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
        }
        for k, v in obj.items():
            if k in runtime_fields:
                continue
            if isinstance(v, dict):
                result[k] = clean_for_apply(v)
            elif isinstance(v, list):
                result[k] = [clean_for_apply(item) for item in v]
            else:
                result[k] = v
        return result

    sanitized = clean_for_apply(parsed)
    yaml_to_apply = yaml.safe_dump(sanitized, sort_keys=False)

    # Build the API URL and use server-side apply
    from urllib.parse import urlencode
    from kubernetes.client import ApiClient

    api_client = k8s.ApiClient() if hasattr(k8s, "ApiClient") else ApiClient()
    base = api_client.configuration.host.rstrip("/")

    # Determine the API path based on resource type
    api_paths = {
        "deployments": f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
        "replicasets": f"/apis/apps/v1/namespaces/{namespace}/replicasets/{name}",
        "pods": f"/api/v1/namespaces/{namespace}/pods/{name}",
        "configmaps": f"/api/v1/namespaces/{namespace}/configmaps/{name}",
        "services": f"/api/v1/namespaces/{namespace}/services/{name}",
        "statefulsets": f"/apis/apps/v1/namespaces/{namespace}/statefulsets/{name}",
        "daemonsets": f"/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}",
        "jobs": f"/apis/batch/v1/namespaces/{namespace}/jobs/{name}",
        "cronjobs": f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{name}",
        "ingresses": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/ingresses/{name}",
        "pv": f"/api/v1/persistentvolumes/{name}",
        "pvc": f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}",
        "storageclasses": f"/apis/storage.k8s.io/v1/storageclasses/{name}",
        "serviceaccounts": f"/api/v1/namespaces/{namespace}/serviceaccounts/{name}",
        "roles": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/roles/{name}",
        "rolebindings": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/rolebindings/{name}",
        "clusterroles": f"/apis/rbac.authorization.k8s.io/v1/clusterroles/{name}",
        "clusterrolebindings": f"/apis/rbac.authorization.k8s.io/v1/clusterrolebindings/{name}",
    }

    if resource not in api_paths:
        raise HTTPException(
            status_code=400, detail=f"Unsupported resource type: {resource}"
        )

    url = api_paths[resource]
    query_params = [("fieldManager", "kube-compass"), ("force", "true")]
    if dry_run:
        query_params.append(("dryRun", "All"))
    url = f"{base}{url}?{urlencode(query_params)}"

    headers = {
        "Content-Type": "application/apply-patch+yaml",
        "Accept": "application/json",
    }

    try:
        resp = api_client.rest_client.pool_manager.request(
            "PATCH",
            url,
            body=yaml_to_apply.encode("utf-8"),
            headers=headers,
        )

        resp_status = resp.status if hasattr(resp, "status") else 200
        resp_bytes = resp.data if hasattr(resp, "data") else resp.read()
        resp_text = (
            resp_bytes.decode("utf-8")
            if hasattr(resp_bytes, "decode")
            else str(resp_bytes)
        )

        if resp_status >= 400:
            raise HTTPException(
                status_code=resp_status,
                detail=f"Kubernetes API returned {resp_status}: {resp_text}",
            )

        if dry_run:
            try:
                preview = json.loads(resp_text)
            except:
                preview = resp_text
            return {"dry_run": True, "preview": preview}

        logger.info(f"Successfully applied {resource}/{name} via server-side apply")

        # Save snapshot for history
        if not dry_run:
            try:
                yaml_after = _fetch_resource_yaml(k8s, resource, name, namespace)
                save_resource_snapshot(
                    request=request,
                    resource_type=resource,
                    resource_name=name,
                    operation="apply",
                    user_email=user_email,
                    yaml_before=yaml_before,
                    yaml_after=yaml_after,
                )
            except Exception as snap_err:
                logger.error(f"Failed to save history snapshot: {snap_err}")

        return {
            "status": "applied",
            "message": f"{resource.capitalize()} {name} updated successfully",
        }

    except Exception as e:
        error_msg = str(e)
        # Handle Kubernetes ApiException which has a 'body' attribute
        if hasattr(e, "body") and e.body:  # type: ignore[attr-defined]
            error_body = e.body  # type: ignore[attr-defined]
            if hasattr(error_body, "decode"):
                error_body = error_body.decode("utf-8")
            error_msg = error_body
        raise HTTPException(status_code=500, detail=error_msg)


@router.delete("/{resource}/{name}")
async def delete_resource(
    resource: str,
    name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit"])),
):
    """Delete a resource by name"""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    k8s = load_k8s_client(cluster["kubeconfig_path"])
    namespace = request.session.get("active_namespace", "default")
    effective_namespace = namespace if namespace != "_all" else "default"

    # Capture snapshot before delete for history
    from app.routes.history import save_resource_snapshot, _fetch_resource_yaml

    user_email = user.get("email") if isinstance(user, dict) else str(user)

    from kubernetes.client import ApiClient

    api_client = k8s.ApiClient() if hasattr(k8s, "ApiClient") else ApiClient()
    base = api_client.configuration.host.rstrip("/")

    api_paths = {
        "pods": f"/api/v1/namespaces/{namespace}/pods/{name}",
        "services": f"/api/v1/namespaces/{namespace}/services/{name}",
        "configmaps": f"/api/v1/namespaces/{namespace}/configmaps/{name}",
        "secrets": f"/api/v1/namespaces/{namespace}/secrets/{name}",
        "deployments": f"/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
        "replicasets": f"/apis/apps/v1/namespaces/{namespace}/replicasets/{name}",
        "statefulsets": f"/apis/apps/v1/namespaces/{namespace}/statefulsets/{name}",
        "daemonsets": f"/apis/apps/v1/namespaces/{namespace}/daemonsets/{name}",
        "jobs": f"/apis/batch/v1/namespaces/{namespace}/jobs/{name}",
        "cronjobs": f"/apis/batch/v1/namespaces/{namespace}/cronjobs/{name}",
        "ingresses": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/ingresses/{name}",
        "pvc": f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}",
        "pv": f"/api/v1/persistentvolumes/{name}",
        "storageclasses": f"/apis/storage.k8s.io/v1/storageclasses/{name}",
        "serviceaccounts": f"/api/v1/namespaces/{namespace}/serviceaccounts/{name}",
        "roles": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/roles/{name}",
        "rolebindings": f"/apis/rbac.authorization.k8s.io/v1/namespaces/{namespace}/rolebindings/{name}",
        "clusterroles": f"/apis/rbac.authorization.k8s.io/v1/clusterroles/{name}",
        "clusterrolebindings": f"/apis/rbac.authorization.k8s.io/v1/clusterrolebindings/{name}",
        "hpas": f"/apis/autoscaling/v2/namespaces/{namespace}/horizontalpodautoscalers/{name}",
        "networkpolicies": f"/apis/networking.k8s.io/v1/namespaces/{namespace}/networkpolicies/{name}",
        "endpoints": f"/api/v1/namespaces/{namespace}/endpoints/{name}",
        "limitranges": f"/api/v1/namespaces/{namespace}/limitranges/{name}",
        "resourcequotas": f"/api/v1/namespaces/{namespace}/resourcequotas/{name}",
    }

    if resource not in api_paths:
        raise HTTPException(
            status_code=400, detail=f"Unsupported resource type: {resource}"
        )

    url = f"{base}{api_paths[resource]}"

    headers = {
        "Accept": "application/json",
    }

    # Snapshot before delete
    yaml_before = _fetch_resource_yaml(k8s, resource, name, namespace)

    try:
        resp = api_client.rest_client.pool_manager.request(
            "DELETE",
            url,
            headers=headers,
        )

        logger.info(f"Successfully deleted {resource}/{name}")

        # Save snapshot for history
        save_resource_snapshot(
            request=request,
            resource_type=resource,
            resource_name=name,
            operation="delete",
            user_email=user_email,
            yaml_before=yaml_before,
        )

        return {
            "status": "deleted",
            "message": f"{resource.capitalize()} {name} deleted successfully",
        }

    except Exception as e:
        error_msg = str(e)
        if hasattr(e, "body") and e.body:
            error_body = e.body
            if hasattr(error_body, "decode"):
                error_body = error_body.decode("utf-8")
            error_msg = error_body
        raise HTTPException(status_code=500, detail=error_msg)
