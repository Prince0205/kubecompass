"""
Topology Graph Routes

Provides REST API endpoints for building Kubernetes resource topology graphs.
Traverses ownerReferences, selectors, and volume mounts to construct a
dependency graph showing how resources relate to each other.

Supported relationships:
- Deployment -> ReplicaSet -> Pod (ownerReferences)
- StatefulSet -> Pod (ownerReferences)
- DaemonSet -> Pod (ownerReferences)
- Job -> Pod (ownerReferences)
- CronJob -> Job (ownerReferences)
- Service -> Pod (via selector matching)
- Ingress -> Service (via backend rules)
- ConfigMap / Secret -> Pod (via volume mounts)
- PVC -> PV (via volume claim)
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging

router = APIRouter(prefix="/api/topology")
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


def _get_pod_status(pod):
    """Determine effective pod status from container states."""
    effective_status = pod.status.phase or "Unknown"
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
                return reason
        elif cs.state and cs.state.terminated:
            reason = cs.state.terminated.reason or ""
            if reason in ("Error", "OOMKilled", "ContainerCannotRun"):
                return reason
    return effective_status


def _status_color(status):
    """Map status to color for frontend visualization."""
    status_lower = (status or "").lower()
    if status_lower in ("running", "active", "healthy", "available", "bound", "true"):
        return "green"
    if status_lower in (
        "failed",
        "error",
        "crashloopbackoff",
        "imagepullbackoff",
        "errimagepull",
        "oomkilled",
        "notready",
    ):
        return "red"
    if status_lower in (
        "pending",
        "containercreating",
        "terminating",
        "progressing",
        "unknown",
    ):
        return "yellow"
    return "gray"


def _make_node(uid, name, kind, namespace, status, extra=None):
    """Create a standardized node entry."""
    return {
        "id": uid,
        "name": name,
        "kind": kind,
        "namespace": namespace,
        "status": status or "Unknown",
        "color": _status_color(status),
        **(extra or {}),
    }


def _make_edge(source_id, target_id, label):
    """Create a standardized edge entry."""
    return {
        "source": source_id,
        "target": target_id,
        "label": label,
    }


@router.get("/graph")
def get_topology_graph(
    request: Request,
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Build the full topology graph for the active namespace or cluster."""
    try:
        k8s, session_ns = get_k8s_context(request)
        ns = namespace or session_ns
        all_ns = ns in ("_all_", "_all")

        v1 = k8s.CoreV1Api()
        apps = k8s.AppsV1Api()
        batch = k8s.BatchV1Api()
        networking = k8s.NetworkingV1Api()

        nodes = []
        edges = []
        node_ids = set()

        def add_node(node):
            if node["id"] not in node_ids:
                node_ids.add(node["id"])
                nodes.append(node)

        def add_edge(edge):
            edges.append(edge)

        # --- Fetch all resources ---
        # Pods
        pods = (
            v1.list_pod_for_all_namespaces().items
            if all_ns
            else v1.list_namespaced_pod(ns).items
        )
        # Deployments
        deployments = (
            apps.list_deployment_for_all_namespaces().items
            if all_ns
            else apps.list_namespaced_deployment(ns).items
        )
        # ReplicaSets
        replicasets = (
            apps.list_replica_set_for_all_namespaces().items
            if all_ns
            else apps.list_namespaced_replica_set(ns).items
        )
        # StatefulSets
        statefulsets = (
            apps.list_stateful_set_for_all_namespaces().items
            if all_ns
            else apps.list_namespaced_stateful_set(ns).items
        )
        # DaemonSets
        daemonsets = (
            apps.list_daemon_set_for_all_namespaces().items
            if all_ns
            else apps.list_namespaced_daemon_set(ns).items
        )
        # Jobs
        jobs = (
            batch.list_job_for_all_namespaces().items
            if all_ns
            else batch.list_namespaced_job(ns).items
        )
        # CronJobs
        cronjobs = (
            batch.list_cron_job_for_all_namespaces().items
            if all_ns
            else batch.list_namespaced_cron_job(ns).items
        )
        # Services
        services = (
            v1.list_service_for_all_namespaces().items
            if all_ns
            else v1.list_namespaced_service(ns).items
        )
        # Ingresses
        try:
            ingresses = (
                networking.list_ingress_for_all_namespaces().items
                if all_ns
                else networking.list_namespaced_ingress(ns).items
            )
        except Exception:
            ingresses = []
        # ConfigMaps
        configmaps = (
            v1.list_config_map_for_all_namespaces().items
            if all_ns
            else v1.list_namespaced_config_map(ns).items
        )
        # Secrets
        secrets = (
            v1.list_secret_for_all_namespaces().items
            if all_ns
            else v1.list_namespaced_secret(ns).items
        )
        # PVCs
        pvcs = (
            v1.list_persistent_volume_claim_for_all_namespaces().items
            if all_ns
            else v1.list_namespaced_persistent_volume_claim(ns).items
        )
        # PVs (cluster-scoped)
        try:
            pvs = v1.list_persistent_volume().items
        except Exception:
            pvs = []

        # --- Build Nodes ---

        # Deployments
        dep_status_map = {}
        for dep in deployments:
            dep_ns = dep.metadata.namespace or "default"
            dep_uid = str(dep.metadata.uid)
            status = "Healthy"
            if dep.status.unavailable_replicas:
                status = "Degraded"
            elif dep.status.updated_replicas != dep.spec.replicas:
                status = "Progressing"
            dep_status_map[dep_uid] = status
            add_node(
                _make_node(
                    dep_uid,
                    dep.metadata.name,
                    "Deployment",
                    dep_ns,
                    status,
                    {"replicas": dep.spec.replicas or 0},
                )
            )

        # ReplicaSets
        rs_status_map = {}
        for rs in replicasets:
            rs_ns = rs.metadata.namespace or "default"
            rs_uid = str(rs.metadata.uid)
            ready = rs.status.ready_replicas or 0
            desired = rs.spec.replicas or 0
            status = "Healthy" if ready >= desired else "Degraded"
            rs_status_map[rs_uid] = status
            add_node(
                _make_node(
                    rs_uid,
                    rs.metadata.name,
                    "ReplicaSet",
                    rs_ns,
                    status,
                    {"ready": ready, "desired": desired},
                )
            )

        # StatefulSets
        for sts in statefulsets:
            sts_ns = sts.metadata.namespace or "default"
            sts_uid = str(sts.metadata.uid)
            ready = sts.status.ready_replicas or 0
            desired = sts.spec.replicas or 0
            status = "Healthy" if ready >= desired else "Degraded"
            add_node(
                _make_node(
                    sts_uid,
                    sts.metadata.name,
                    "StatefulSet",
                    sts_ns,
                    status,
                    {"ready": ready, "desired": desired},
                )
            )

        # DaemonSets
        for ds in daemonsets:
            ds_ns = ds.metadata.namespace or "default"
            ds_uid = str(ds.metadata.uid)
            desired = ds.status.desired_number_scheduled or 0
            ready = ds.status.number_ready or 0
            status = "Healthy" if ready >= desired and desired > 0 else "Degraded"
            add_node(
                _make_node(
                    ds_uid,
                    ds.metadata.name,
                    "DaemonSet",
                    ds_ns,
                    status,
                    {"ready": ready, "desired": desired},
                )
            )

        # Jobs
        for job in jobs:
            job_ns = job.metadata.namespace or "default"
            job_uid = str(job.metadata.uid)
            succeeded = job.status.succeeded or 0
            failed = job.status.failed or 0
            completions = job.spec.completions or 1
            if failed > 0:
                status = "Failed"
            elif succeeded >= completions:
                status = "Succeeded"
            elif (job.status.active or 0) > 0:
                status = "Active"
            else:
                status = "Pending"
            add_node(
                _make_node(
                    job_uid,
                    job.metadata.name,
                    "Job",
                    job_ns,
                    status,
                    {"succeeded": succeeded, "failed": failed},
                )
            )

        # CronJobs
        for cj in cronjobs:
            cj_ns = cj.metadata.namespace or "default"
            cj_uid = str(cj.metadata.uid)
            active_jobs = len(cj.status.active or [])
            status = "Active" if active_jobs > 0 else "Idle"
            add_node(
                _make_node(
                    cj_uid,
                    cj.metadata.name,
                    "CronJob",
                    cj_ns,
                    status,
                    {"schedule": cj.spec.schedule, "active": active_jobs},
                )
            )

        # Services
        svc_selector_map = {}
        for svc in services:
            svc_ns = svc.metadata.namespace or "default"
            svc_uid = str(svc.metadata.uid)
            svc_type = svc.spec.type or "ClusterIP"
            raw_selector = svc.spec.selector or {}
            if isinstance(raw_selector, dict):
                selector = raw_selector
            elif hasattr(raw_selector, "match_labels"):
                selector = raw_selector.match_labels or {}
            else:
                selector = {}
            svc_selector_map[svc_uid] = {
                "selector": selector,
                "namespace": svc_ns,
                "name": svc.metadata.name,
            }
            add_node(
                _make_node(
                    svc_uid,
                    svc.metadata.name,
                    "Service",
                    svc_ns,
                    "Active",
                    {"service_type": svc_type, "cluster_ip": svc.spec.cluster_ip},
                )
            )

        # Ingresses
        for ing in ingresses:
            ing_ns = ing.metadata.namespace or "default"
            ing_uid = str(ing.metadata.uid)
            add_node(
                _make_node(
                    ing_uid,
                    ing.metadata.name,
                    "Ingress",
                    ing_ns,
                    "Active",
                )
            )

        # ConfigMaps
        cm_set = set()
        for cm in configmaps:
            cm_ns = cm.metadata.namespace or "default"
            cm_uid = str(cm.metadata.uid)
            cm_set.add((cm.metadata.name, cm_ns))
            add_node(_make_node(cm_uid, cm.metadata.name, "ConfigMap", cm_ns, "Active"))

        # Secrets
        secret_set = set()
        for sec in secrets:
            sec_ns = sec.metadata.namespace or "default"
            sec_uid = str(sec.metadata.uid)
            secret_set.add((sec.metadata.name, sec_ns))
            add_node(_make_node(sec_uid, sec.metadata.name, "Secret", sec_ns, "Active"))

        # PVCs
        pvc_map = {}
        for pvc in pvcs:
            pvc_ns = pvc.metadata.namespace or "default"
            pvc_uid = str(pvc.metadata.uid)
            phase = pvc.status.phase or "Unknown"
            pvc_name = pvc.metadata.name
            pv_name = pvc.spec.volume_name
            pvc_map[(pvc_name, pvc_ns)] = pv_name
            add_node(
                _make_node(
                    pvc_uid,
                    pvc_name,
                    "PersistentVolumeClaim",
                    pvc_ns,
                    phase,
                )
            )

        # PVs - only include PVs that are bound to PVCs in the current scope
        pv_map = {}
        pv_names_in_scope = set(pvc_map.values())
        for pv in pvs:
            pv_name = pv.metadata.name
            if pv_name not in pv_names_in_scope:
                continue
            pv_uid = str(pv.metadata.uid)
            phase = pv.status.phase or "Unknown"
            pv_map[pv_name] = pv_uid
            add_node(_make_node(pv_uid, pv_name, "PersistentVolume", "", phase))

        # Pods - with volume and owner tracking
        pod_selector_map = {}
        for pod in pods:
            pod_ns = pod.metadata.namespace or "default"
            pod_uid = str(pod.metadata.uid)
            status = _get_pod_status(pod)

            # Collect selectors for service matching
            labels = pod.metadata.labels or {}
            pod_selector_map[pod_uid] = {
                "labels": labels,
                "namespace": pod_ns,
            }

            # Track volume mounts for ConfigMap/Secret/PVC links
            volumes_configmaps = []
            volumes_secrets = []
            volumes_pvcs = []
            pod_volumes = getattr(pod.spec, "volumes", None) or []
            if pod_volumes:
                for vol in pod_volumes:
                    if vol.config_map:
                        volumes_configmaps.append(vol.config_map.name)
                    if vol.secret:
                        volumes_secrets.append(vol.secret.secret_name)
                    if vol.persistent_volume_claim:
                        volumes_pvcs.append(vol.persistent_volume_claim.claim_name)

            add_node(
                _make_node(
                    pod_uid,
                    pod.metadata.name,
                    "Pod",
                    pod_ns,
                    status,
                    {
                        "node": pod.spec.node_name or "Unscheduled",
                        "restarts": sum(
                            cs.restart_count
                            for cs in (pod.status.container_statuses or [])
                        ),
                    },
                )
            )

            # Edge: Pod -> ConfigMap (volume mount)
            for cm_name in volumes_configmaps:
                cm_uid = f"cm-{pod_ns}-{cm_name}"
                # Find actual UID from configmaps list
                for cm in configmaps:
                    if (
                        cm.metadata.name == cm_name
                        and (cm.metadata.namespace or "default") == pod_ns
                    ):
                        cm_uid = str(cm.metadata.uid)
                        break
                if cm_uid in node_ids:
                    add_edge(_make_edge(pod_uid, cm_uid, "mounts"))

            # Edge: Pod -> Secret (volume mount)
            for sec_name in volumes_secrets:
                sec_uid = f"sec-{pod_ns}-{sec_name}"
                for sec in secrets:
                    if (
                        sec.metadata.name == sec_name
                        and (sec.metadata.namespace or "default") == pod_ns
                    ):
                        sec_uid = str(sec.metadata.uid)
                        break
                if sec_uid in node_ids:
                    add_edge(_make_edge(pod_uid, sec_uid, "mounts"))

            # Edge: Pod -> PVC (volume claim)
            for pvc_name in volumes_pvcs:
                pvc_uid = f"pvc-{pod_ns}-{pvc_name}"
                for pvc in pvcs:
                    if (
                        pvc.metadata.name == pvc_name
                        and (pvc.metadata.namespace or "default") == pod_ns
                    ):
                        pvc_uid = str(pvc.metadata.uid)
                        break
                if pvc_uid in node_ids:
                    add_edge(_make_edge(pod_uid, pvc_uid, "claims"))

            # Owner references
            if pod.metadata.owner_references:
                for owner_ref in pod.metadata.owner_references:
                    owner_uid = str(owner_ref.uid)
                    if owner_uid in node_ids:
                        add_edge(_make_edge(owner_uid, pod_uid, "owns"))

        # --- Build edges from owner references (non-pod) ---
        # ReplicaSet -> Deployment
        for rs in replicasets:
            rs_uid = str(rs.metadata.uid)
            if rs.metadata.owner_references:
                for owner_ref in rs.metadata.owner_references:
                    owner_uid = str(owner_ref.uid)
                    if owner_uid in node_ids:
                        add_edge(_make_edge(owner_uid, rs_uid, "owns"))

        # Job -> CronJob
        for job in jobs:
            job_uid = str(job.metadata.uid)
            if job.metadata.owner_references:
                for owner_ref in job.metadata.owner_references:
                    owner_uid = str(owner_ref.uid)
                    if owner_uid in node_ids:
                        add_edge(_make_edge(owner_uid, job_uid, "owns"))

        # --- Service -> Pod (selector matching) ---
        for svc_uid, svc_info in svc_selector_map.items():
            selector = svc_info["selector"]
            if not selector:
                continue
            for pod_uid, pod_info in pod_selector_map.items():
                if pod_info["namespace"] != svc_info["namespace"]:
                    continue
                labels = pod_info["labels"]
                match = all(labels.get(k) == v for k, v in selector.items())
                if match:
                    add_edge(_make_edge(svc_uid, pod_uid, "selector"))

        # --- Ingress -> Service ---
        for ing in ingresses:
            ing_uid = str(ing.metadata.uid)
            ing_ns = ing.metadata.namespace or "default"
            if ing.spec.rules:
                for rule in ing.spec.rules:
                    if rule.http and rule.http.paths:
                        for path in rule.http.paths:
                            svc_name = None
                            if path.backend and path.backend.service:
                                svc_name = path.backend.service.name
                            if svc_name:
                                for svc_uid, svc_info in svc_selector_map.items():
                                    if (
                                        svc_info["name"] == svc_name
                                        and svc_info["namespace"] == ing_ns
                                    ):
                                        add_edge(_make_edge(ing_uid, svc_uid, "routes"))

        # --- PVC -> PV ---
        for (pvc_name, pvc_ns), pv_name in pvc_map.items():
            if pv_name and pv_name in pv_map:
                pvc_uid = f"pvc-{pvc_ns}-{pvc_name}"
                pv_uid = pv_map[pv_name]
                for pvc in pvcs:
                    if (
                        pvc.metadata.name == pvc_name
                        and (pvc.metadata.namespace or "default") == pvc_ns
                    ):
                        pvc_uid = str(pvc.metadata.uid)
                        break
                if pvc_uid in node_ids and pv_uid in node_ids:
                    add_edge(_make_edge(pvc_uid, pv_uid, "bound"))

        return {
            "nodes": nodes,
            "edges": edges,
            "namespace": ns,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building topology graph: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to build topology graph: {str(e)}")
