"""
Network Resource Management Endpoints
Handles: Services, Endpoints, Ingresses, NetworkPolicies
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from kubernetes.client.rest import ApiException
from app.auth.rbac import require_role
from app.auth.session import get_current_user
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging

router = APIRouter(prefix="/api/resources/network", tags=["network"])
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
# SERVICE ENDPOINTS
# =============================================================================


@router.get("/services")
async def list_services(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all Services in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        services = v1.list_namespaced_service(namespace)

        result = []
        for svc in services.items:
            result.append(
                {
                    "name": svc.metadata.name,
                    "namespace": svc.metadata.namespace,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip,
                    "ports": len(svc.spec.ports) if svc.spec.ports else 0,
                    "created": svc.metadata.creation_timestamp,
                }
            )
        return {"services": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Services: {str(e)}")


@router.get("/services/{name}")
async def get_service_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get Service detail including port information"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        svc = v1.read_namespaced_service(name, namespace)

        return {
            "kind": "Service",
            "apiVersion": "v1",
            "metadata": {
                "name": svc.metadata.name,
                "namespace": svc.metadata.namespace,
                "labels": svc.metadata.labels or {},
                "annotations": svc.metadata.annotations or {},
                "uid": str(svc.metadata.uid) if svc.metadata.uid else None,
                "creationTimestamp": svc.metadata.creation_timestamp.isoformat()
                if svc.metadata.creation_timestamp
                else None,
            },
            "spec": {
                "type": svc.spec.type,
                "clusterIP": svc.spec.cluster_ip,
                "externalIPs": svc.spec.external_i_ps or [],
                "selector": svc.spec.selector or {},
                "ports": [
                    {
                        "port": p.port,
                        "targetPort": str(p.target_port) if p.target_port else None,
                        "protocol": p.protocol or "TCP",
                        "name": p.name,
                    }
                    for p in (svc.spec.ports or [])
                ],
            },
            "status": {},
            "age": str(svc.metadata.creation_timestamp)
            if svc.metadata.creation_timestamp
            else None,
            "created": svc.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting Service: {str(e)}")


@router.delete("/services/{name}")
async def delete_service(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete a Service"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        v1.delete_namespaced_service(name, namespace)

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Service '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting Service: {str(e)}")


# =============================================================================
# ENDPOINTS ENDPOINTS
# =============================================================================


@router.get("/endpoints")
async def list_endpoints(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all Endpoints in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        v1 = k8s.CoreV1Api()
        endpoints = v1.list_namespaced_endpoints(namespace)

        result = []
        for ep in endpoints.items:
            address_count = 0
            if ep.subsets:
                for subset in ep.subsets:
                    if subset.addresses:
                        address_count += len(subset.addresses)

            result.append(
                {
                    "name": ep.metadata.name,
                    "namespace": ep.metadata.namespace,
                    "addresses": address_count,
                    "created": ep.metadata.creation_timestamp,
                }
            )
        return {"endpoints": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing Endpoints: {str(e)}"
        )


@router.get("/endpoints/{name}")
async def get_endpoints_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get Endpoints detail with address information"""
    k8s, namespace = get_k8s_context(request)

    try:
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
                                "target_ref": addr.target_ref.name
                                if addr.target_ref
                                else None,
                            }
                        )

                ports = []
                if subset.ports:
                    for port in subset.ports:
                        ports.append(
                            {"port": port.port, "protocol": port.protocol or "TCP"}
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
                "uid": str(ep.metadata.uid) if ep.metadata.uid else None,
                "creationTimestamp": ep.metadata.creation_timestamp.isoformat()
                if ep.metadata.creation_timestamp
                else None,
            },
            "subsets": subsets_data,
            "created": ep.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Endpoints '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting Endpoints: {str(e)}"
        )


# =============================================================================
# INGRESS ENDPOINTS
# =============================================================================


@router.get("/ingresses")
async def list_ingresses(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all Ingresses in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        networking = k8s.NetworkingV1Api()
        ingresses = networking.list_namespaced_ingress(namespace)

        result = []
        for ing in ingresses.items:
            hosts = []
            if ing.spec.rules:
                hosts = [rule.host for rule in ing.spec.rules if rule.host]

            result.append(
                {
                    "name": ing.metadata.name,
                    "namespace": ing.metadata.namespace,
                    "hosts": hosts,
                    "tls_enabled": bool(ing.spec.tls),
                    "created": ing.metadata.creation_timestamp,
                }
            )
        return {"ingresses": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing Ingresses: {str(e)}"
        )


@router.get("/ingresses/{name}")
async def get_ingress_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get Ingress detail with routing rules"""
    k8s, namespace = get_k8s_context(request)

    try:
        networking = k8s.NetworkingV1Api()
        ing = networking.read_namespaced_ingress(name, namespace)

        rules = []
        if ing.spec.rules:
            for rule in ing.spec.rules:
                paths = []
                if rule.http and rule.http.paths:
                    for path in rule.http.paths:
                        paths.append(
                            {
                                "path": path.path,
                                "path_type": path.path_type or "Prefix",
                                "backend_service": path.backend.service.name
                                if path.backend.service
                                else None,
                                "backend_port": path.backend.service.port.number
                                if path.backend.service and path.backend.service.port
                                else None,
                            }
                        )

                rules.append({"host": rule.host, "paths": paths})

        tls_hosts = []
        if ing.spec.tls:
            for tls in ing.spec.tls:
                tls_hosts.append(
                    {"hosts": tls.hosts or [], "secret_name": tls.secret_name}
                )

        return {
            "kind": "Ingress",
            "apiVersion": "networking.k8s.io/v1",
            "metadata": {
                "name": ing.metadata.name,
                "namespace": ing.metadata.namespace,
                "labels": ing.metadata.labels or {},
                "annotations": ing.metadata.annotations or {},
                "uid": str(ing.metadata.uid) if ing.metadata.uid else None,
                "creationTimestamp": ing.metadata.creation_timestamp.isoformat()
                if ing.metadata.creation_timestamp
                else None,
            },
            "rules": rules,
            "tls": tls_hosts,
            "created": ing.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Ingress '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting Ingress: {str(e)}")


@router.delete("/ingresses/{name}")
async def delete_ingress(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit"])),
):
    """Delete an Ingress"""
    k8s, namespace = get_k8s_context(request)

    try:
        networking = k8s.NetworkingV1Api()
        networking.delete_namespaced_ingress(name, namespace)

        return {"status": "deleted", "name": name}
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"Ingress '{name}' not found")
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting Ingress: {str(e)}")


# =============================================================================
# NETWORKPOLICY ENDPOINTS
# =============================================================================


@router.get("/networkpolicies")
async def list_network_policies(
    request: Request, current_user=Depends(require_role(["admin", "edit", "view"]))
):
    """List all NetworkPolicies in the current namespace"""
    k8s, namespace = get_k8s_context(request)

    try:
        networking = k8s.NetworkingV1Api()
        policies = networking.list_namespaced_network_policy(namespace)

        result = []
        for policy in policies.items:
            result.append(
                {
                    "name": policy.metadata.name,
                    "namespace": policy.metadata.namespace,
                    "policy_types": policy.spec.policy_types or [],
                    "created": policy.metadata.creation_timestamp,
                }
            )
        return {"networkpolicies": result}
    except ApiException as e:
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing NetworkPolicies: {str(e)}"
        )


@router.get("/networkpolicies/{name}")
async def get_network_policy_detail(
    name: str,
    request: Request,
    current_user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get NetworkPolicy detail with ingress/egress rules"""
    k8s, namespace = get_k8s_context(request)

    try:
        networking = k8s.NetworkingV1Api()
        policy = networking.read_namespaced_network_policy(name, namespace)

        def format_selector(selector):
            if not selector:
                return {}
            return {
                "match_labels": selector.match_labels or {},
                "match_expressions": selector.match_expressions or [],
            }

        return {
            "name": policy.metadata.name,
            "namespace": policy.metadata.namespace,
            "labels": policy.metadata.labels or {},
            "annotations": policy.metadata.annotations or {},
            "pod_selector": format_selector(policy.spec.pod_selector),
            "policy_types": policy.spec.policy_types or [],
            "ingress": [
                {"from": [format_selector(f.pod_selector) for f in (rule.from_ or [])]}
                for rule in (policy.spec.ingress or [])
            ],
            "egress": [
                {"to": [format_selector(t.pod_selector) for t in (rule.to or [])]}
                for rule in (policy.spec.egress or [])
            ],
            "created": policy.metadata.creation_timestamp,
        }
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"NetworkPolicy '{name}' not found"
            )
        raise HTTPException(
            status_code=e.status, detail=f"Kubernetes API error: {e.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting NetworkPolicy: {str(e)}"
        )
