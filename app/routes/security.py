"""
Security Scanner Routes

Provides REST API endpoints for cluster security scanning:
- Pod security checks (root, privileged, resource limits, secrets as env vars)
- Service security checks (missing NetworkPolicies)
- RBAC analysis (over-permissioned bindings)
- Image trust checks (untrusted registries)
- Node version checks (outdated Kubernetes versions)
- PodDisruptionBudget coverage checks

Returns findings with severity levels and a 0-100 security score.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import logging
import re
from datetime import datetime, timezone

router = APIRouter(prefix="/api/security")
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


def severity_weight(severity):
    """Return numeric weight for severity scoring."""
    return {"critical": 10, "high": 5, "medium": 3, "low": 1, "info": 0}.get(
        severity, 0
    )


def check_pod_security(v1, namespace):
    """Check pods for security issues."""
    findings = []

    try:
        if namespace == "_all":
            pods = v1.list_pod_for_all_namespaces().items
        else:
            pods = v1.list_namespaced_pod(namespace).items
    except Exception as e:
        logger.error(f"Failed to list pods: {e}")
        return findings

    for pod in pods:
        pod_name = pod.metadata.name
        ns = pod.metadata.namespace or namespace
        spec = pod.spec

        if not spec or not spec.containers:
            continue

        # Check if pod runs as root
        security_context = spec.security_context
        run_as_root = False
        if security_context:
            if security_context.run_as_non_root is False:
                run_as_root = True
            if security_context.run_as_user == 0:
                run_as_root = True

        for container in spec.containers or []:
            container_name = container.name
            cs = container.security_context

            # Check running as root
            if cs and cs.run_as_user == 0:
                run_as_root = True
            if cs and cs.run_as_non_root is False:
                run_as_root = True

            if run_as_root:
                findings.append(
                    {
                        "id": f"pod-root-{ns}-{pod_name}-{container_name}",
                        "severity": "critical",
                        "category": "Pod Security",
                        "title": "Container running as root",
                        "description": f"Container '{container_name}' in pod '{pod_name}' is configured to run as root user (UID 0). This increases the blast radius if the container is compromised.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Set runAsNonRoot: true and runAsUser to a non-zero UID in the pod or container security context.",
                    }
                )

            # Check privileged containers
            if cs and cs.privileged:
                findings.append(
                    {
                        "id": f"pod-privileged-{ns}-{pod_name}-{container_name}",
                        "severity": "critical",
                        "category": "Pod Security",
                        "title": "Privileged container",
                        "description": f"Container '{container_name}' in pod '{pod_name}' is running in privileged mode. This gives the container full access to the host.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Remove privileged: true and use specific capabilities instead.",
                    }
                )

            # Check missing resource limits
            if not container.resources or not container.resources.limits:
                findings.append(
                    {
                        "id": f"pod-no-limits-{ns}-{pod_name}-{container_name}",
                        "severity": "medium",
                        "category": "Resource Limits",
                        "title": "Container without resource limits",
                        "description": f"Container '{container_name}' in pod '{pod_name}' has no resource limits set. This can lead to resource exhaustion and noisy-neighbor issues.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Set CPU and memory limits for all containers.",
                    }
                )
            else:
                limits = container.resources.limits
                if limits.get("memory") is None and limits.get("cpu") is None:
                    findings.append(
                        {
                            "id": f"pod-no-mem-cpu-limits-{ns}-{pod_name}-{container_name}",
                            "severity": "medium",
                            "category": "Resource Limits",
                            "title": "Container missing CPU/memory limits",
                            "description": f"Container '{container_name}' in pod '{pod_name}' has resource limits but is missing CPU and/or memory limits.",
                            "resource": f"{ns}/{pod_name}",
                            "resource_kind": "Pod",
                            "namespace": ns,
                            "recommendation": "Set explicit CPU and memory limits.",
                        }
                    )

            # Check secrets as environment variables
            if container.env:
                for env_var in container.env:
                    if env_var.value_from and env_var.value_from.secret_key_ref:
                        findings.append(
                            {
                                "id": f"pod-secret-env-{ns}-{pod_name}-{container_name}-{env_var.name}",
                                "severity": "high",
                                "category": "Secret Management",
                                "title": "Secret exposed as environment variable",
                                "description": f"Container '{container_name}' in pod '{pod_name}' uses secret '{env_var.value_from.secret_key_ref.name}' as environment variable '{env_var.name}'. Environment variables can leak in logs, crash dumps, and process listings.",
                                "resource": f"{ns}/{pod_name}",
                                "resource_kind": "Pod",
                                "namespace": ns,
                                "recommendation": "Mount secrets as volume files instead of environment variables when possible.",
                            }
                        )

            # Check writable root filesystem
            if cs and cs.read_only_root_filesystem is False:
                findings.append(
                    {
                        "id": "pod-writable-rootfs",
                        "severity": "low",
                        "category": "Pod Security",
                        "title": "Writable root filesystem",
                        "description": f"Container '{container_name}' in pod '{pod_name}' has explicitly set readOnlyRootFilesystem to false.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Set readOnlyRootFilesystem: true and use emptyDir volumes for writable paths.",
                    }
                )

            # Check if allowPrivilegeEscalation is true
            if cs and cs.allow_privilege_escalation:
                findings.append(
                    {
                        "id": f"pod-priv-escalation-{ns}-{pod_name}-{container_name}",
                        "severity": "high",
                        "category": "Pod Security",
                        "title": "Privilege escalation allowed",
                        "description": f"Container '{container_name}' in pod '{pod_name}' allows privilege escalation.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Set allowPrivilegeEscalation: false.",
                    }
                )

        # Check host networking
        if spec.host_network:
            findings.append(
                {
                    "id": f"pod-host-network-{ns}-{pod_name}",
                    "severity": "high",
                    "category": "Pod Security",
                    "title": "Pod using host networking",
                    "description": f"Pod '{pod_name}' is using the host network namespace. This bypasses network policies and gives access to network traffic of other pods.",
                    "resource": f"{ns}/{pod_name}",
                    "resource_kind": "Pod",
                    "namespace": ns,
                    "recommendation": "Avoid hostNetwork: true unless absolutely necessary.",
                }
            )

        # Check host PID
        if spec.host_pid:
            findings.append(
                {
                    "id": f"pod-host-pid-{ns}-{pod_name}",
                    "severity": "high",
                    "category": "Pod Security",
                    "title": "Pod using host PID namespace",
                    "description": f"Pod '{pod_name}' shares the host PID namespace, allowing it to see and signal all processes on the host.",
                    "resource": f"{ns}/{pod_name}",
                    "resource_kind": "Pod",
                    "namespace": ns,
                    "recommendation": "Avoid hostPID: true.",
                }
            )

        # Check host IPC
        if spec.host_ipc:
            findings.append(
                {
                    "id": f"pod-host-ipc-{ns}-{pod_name}",
                    "severity": "medium",
                    "category": "Pod Security",
                    "title": "Pod using host IPC namespace",
                    "description": f"Pod '{pod_name}' shares the host IPC namespace.",
                    "resource": f"{ns}/{pod_name}",
                    "resource_kind": "Pod",
                    "namespace": ns,
                    "recommendation": "Avoid hostIPC: true.",
                }
            )

    return findings


def check_service_network_policies(v1, networking_v1, namespace):
    """Check services that lack NetworkPolicies."""
    findings = []

    try:
        if namespace == "_all":
            services = v1.list_service_for_all_namespaces().items
            netpols = networking_v1.list_network_policy_for_all_namespaces().items
        else:
            services = v1.list_namespaced_service(namespace).items
            netpols = networking_v1.list_namespaced_network_policy(namespace).items
    except Exception as e:
        logger.error(f"Failed to list services/networkpolicies: {e}")
        return findings

    # Build map of namespaces that have NetworkPolicies
    namespaces_with_netpol = set()
    for np in netpols:
        ns = np.metadata.namespace
        if np.spec.pod_selector:
            namespaces_with_netpol.add(ns)

    for svc in services:
        svc_name = svc.metadata.name
        ns = svc.metadata.namespace

        # Skip kubernetes default service
        if svc_name == "kubernetes" and ns == "default":
            continue

        if ns not in namespaces_with_netpol:
            findings.append(
                {
                    "id": f"svc-no-netpol-{ns}-{svc_name}",
                    "severity": "medium",
                    "category": "Network Security",
                    "title": "Service without NetworkPolicy protection",
                    "description": f"Service '{svc_name}' in namespace '{ns}' has no NetworkPolicy restricting traffic. All traffic is allowed by default.",
                    "resource": f"{ns}/{svc_name}",
                    "resource_kind": "Service",
                    "namespace": ns,
                    "recommendation": "Create a NetworkPolicy to restrict ingress/egress traffic for this namespace.",
                }
            )

    return findings


def check_rbac_security(rbac_api, v1_auth):
    """Check for over-permissioned RBAC bindings."""
    findings = []

    try:
        cluster_role_bindings = rbac_api.list_cluster_role_binding().items
        role_bindings = rbac_api.list_role_binding_for_all_namespaces().items
    except Exception as e:
        logger.error(f"Failed to list RBAC bindings: {e}")
        return findings

    dangerous_roles = {"cluster-admin", "admin"}

    # Check ClusterRoleBindings
    for crb in cluster_role_bindings:
        role_name = crb.role_ref.name if crb.role_ref else ""
        if role_name in dangerous_roles:
            subjects = crb.subjects or []
            for subject in subjects:
                subject_name = subject.name or "unknown"
                subject_kind = subject.kind or "unknown"
                findings.append(
                    {
                        "id": f"rbac-cluster-admin-{crb.metadata.name}-{subject_name}",
                        "severity": "high"
                        if role_name == "cluster-admin"
                        else "medium",
                        "category": "RBAC",
                        "title": f"Cluster-wide {role_name} role binding",
                        "description": f"{subject_kind} '{subject_name}' has cluster-wide '{role_name}' permissions through ClusterRoleBinding '{crb.metadata.name}'. This grants unrestricted access to all resources.",
                        "resource": crb.metadata.name,
                        "resource_kind": "ClusterRoleBinding",
                        "namespace": "",
                        "recommendation": "Apply the principle of least privilege. Create specific RoleBindings with only required permissions.",
                    }
                )

    # Check namespace RoleBindings for admin
    for rb in role_bindings:
        role_name = rb.role_ref.name if rb.role_ref else ""
        if role_name in dangerous_roles:
            ns = rb.metadata.namespace
            subjects = rb.subjects or []
            for subject in subjects:
                subject_name = subject.name or "unknown"
                subject_kind = subject.kind or "unknown"
                findings.append(
                    {
                        "id": f"rbac-ns-admin-{ns}-{rb.metadata.name}-{subject_name}",
                        "severity": "medium",
                        "category": "RBAC",
                        "title": f"Namespace-level {role_name} role binding",
                        "description": f"{subject_kind} '{subject_name}' has '{role_name}' permissions in namespace '{ns}' through RoleBinding '{rb.metadata.name}'.",
                        "resource": f"{ns}/{rb.metadata.name}",
                        "resource_kind": "RoleBinding",
                        "namespace": ns,
                        "recommendation": "Consider using more specific roles instead of '{role_name}'.",
                    }
                )

    return findings


def check_image_trust(v1, namespace):
    """Check for containers using images from untrusted registries."""
    findings = []

    trusted_patterns = [
        r"^docker\.io/library/",
        r"^gcr\.io/",
        r"^registry\.k8s\.io/",
        r"^quay\.io/",
        r"^ghcr\.io/",
        r"^public\.ecr\.aws/",
    ]

    try:
        if namespace == "_all":
            pods = v1.list_pod_for_all_namespaces().items
        else:
            pods = v1.list_namespaced_pod(namespace).items
    except Exception as e:
        logger.error(f"Failed to list pods: {e}")
        return findings

    for pod in pods:
        pod_name = pod.metadata.name
        ns = pod.metadata.namespace or namespace

        for container in pod.spec.containers or []:
            image = container.image or ""
            container_name = container.name

            # Check for latest tag
            if image.endswith(":latest") or (":" not in image and "@" not in image):
                findings.append(
                    {
                        "id": f"img-latest-{ns}-{pod_name}-{container_name}",
                        "severity": "medium",
                        "category": "Image Security",
                        "title": "Container using ':latest' tag",
                        "description": f"Container '{container_name}' in pod '{pod_name}' uses image '{image}' with the ':latest' tag or no tag. This makes deployments non-reproducible and can lead to unexpected changes.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Pin images to specific version tags or digests.",
                    }
                )

            # Check for untrusted registries
            is_trusted = False
            for pattern in trusted_patterns:
                if re.match(pattern, image):
                    is_trusted = True
                    break

            # Docker Hub images without explicit registry are implicitly trusted (library images)
            if "/" not in image.split(":")[0] or image.startswith("docker.io/"):
                is_trusted = True

            if not is_trusted and image:
                registry = image.split("/")[0] if "/" in image else "unknown"
                findings.append(
                    {
                        "id": f"img-untrusted-{ns}-{pod_name}-{container_name}",
                        "severity": "low",
                        "category": "Image Security",
                        "title": "Image from untrusted registry",
                        "description": f"Container '{container_name}' in pod '{pod_name}' uses image '{image}' from registry '{registry}' which is not in the default trusted list.",
                        "resource": f"{ns}/{pod_name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Verify the registry is trusted. Consider adding to the trusted registry list.",
                    }
                )

            # Check for images without digest (mutable)
            if "@" not in image and ":" in image:
                tag = image.split(":")[-1]
                if tag != "latest":
                    findings.append(
                        {
                            "id": f"img-no-digest-{ns}-{pod_name}-{container_name}",
                            "severity": "info",
                            "category": "Image Security",
                            "title": "Image not pinned by digest",
                            "description": f"Container '{container_name}' in pod '{pod_name}' uses image '{image}' by tag only. Tags can be overwritten, making builds non-reproducible.",
                            "resource": f"{ns}/{pod_name}",
                            "resource_kind": "Pod",
                            "namespace": ns,
                            "recommendation": "For production, pin images by SHA256 digest for immutability.",
                        }
                    )

    return findings


def check_pdb_coverage(apps_v1, policy_v1, namespace):
    """Check workloads missing PodDisruptionBudgets."""
    findings = []

    try:
        if namespace == "_all":
            deployments = apps_v1.list_deployment_for_all_namespaces().items
            statefulsets = apps_v1.list_stateful_set_for_all_namespaces().items
            pdbs = policy_v1.list_pod_disruption_budget_for_all_namespaces().items
        else:
            deployments = apps_v1.list_namespaced_deployment(namespace).items
            statefulsets = apps_v1.list_namespaced_stateful_set(namespace).items
            pdbs = policy_v1.list_namespaced_pod_disruption_budget(namespace).items
    except Exception as e:
        logger.error(f"Failed to list workloads/PDBs: {e}")
        return findings

    # Build set of (namespace, label-selector-keys) covered by PDBs
    pdb_coverage = set()
    for pdb in pdbs:
        ns = pdb.metadata.namespace
        if pdb.spec.selector and pdb.spec.selector.match_labels:
            selector_keys = frozenset(pdb.spec.selector.match_labels.keys())
            pdb_coverage.add((ns, selector_keys))

    # Check deployments with >1 replica
    for dep in deployments:
        replicas = dep.spec.replicas or 0
        if replicas <= 1:
            continue
        ns = dep.metadata.namespace
        name = dep.metadata.name

        # Check if any PDB covers this deployment's labels
        dep_labels = (
            dep.spec.template.metadata.labels
            if dep.spec.template and dep.spec.template.metadata
            else {}
        )
        covered = False
        for pdb_ns, selector_keys in pdb_coverage:
            if pdb_ns == ns and selector_keys.issubset(frozenset(dep_labels.keys())):
                covered = True
                break

        if not covered:
            findings.append(
                {
                    "id": f"pdb-dep-{ns}-{name}",
                    "severity": "low",
                    "category": "Availability",
                    "title": "Deployment missing PodDisruptionBudget",
                    "description": f"Deployment '{name}' in namespace '{ns}' has {replicas} replicas but no PodDisruptionBudget. During voluntary disruptions (node drains, upgrades), all pods could go down simultaneously.",
                    "resource": f"{ns}/{name}",
                    "resource_kind": "Deployment",
                    "namespace": ns,
                    "recommendation": f"Create a PodDisruptionBudget with minAvailable: 1 or maxUnavailable: 1 for this deployment.",
                }
            )

    # Check statefulsets with >1 replica
    for sts in statefulsets:
        replicas = sts.spec.replicas or 0
        if replicas <= 1:
            continue
        ns = sts.metadata.namespace
        name = sts.metadata.name

        sts_labels = (
            sts.spec.template.metadata.labels
            if sts.spec.template and sts.spec.template.metadata
            else {}
        )
        covered = False
        for pdb_ns, selector_keys in pdb_coverage:
            if pdb_ns == ns and selector_keys.issubset(frozenset(sts_labels.keys())):
                covered = True
                break

        if not covered:
            findings.append(
                {
                    "id": f"pdb-sts-{ns}-{name}",
                    "severity": "low",
                    "category": "Availability",
                    "title": "StatefulSet missing PodDisruptionBudget",
                    "description": f"StatefulSet '{name}' in namespace '{ns}' has {replicas} replicas but no PodDisruptionBudget.",
                    "resource": f"{ns}/{name}",
                    "resource_kind": "StatefulSet",
                    "namespace": ns,
                    "recommendation": f"Create a PodDisruptionBudget for this StatefulSet.",
                }
            )

    return findings


def check_node_versions(v1):
    """Check for nodes running outdated Kubernetes versions."""
    findings = []

    try:
        nodes = v1.list_node().items
    except Exception as e:
        logger.error(f"Failed to list nodes: {e}")
        return findings

    for node in nodes:
        node_name = node.metadata.name
        node_info = node.status.node_info if node.status else None
        if not node_info:
            continue

        kubelet_version = node_info.kubelet_version or ""
        # Parse version like "v1.28.3"
        version_match = re.match(r"v(\d+)\.(\d+)\.(\d+)", kubelet_version)
        if not version_match:
            continue

        major = int(version_match.group(1))
        minor = int(version_match.group(2))
        patch = int(version_match.group(3))

        # Flag if version is older than 1.27 (as of 2026, anything below 1.29 is getting old)
        if major == 1 and minor < 28:
            severity = "high" if minor < 27 else "medium"
            findings.append(
                {
                    "id": f"node-version-{node_name}",
                    "severity": severity,
                    "category": "Node Security",
                    "title": "Outdated Kubernetes version",
                    "description": f"Node '{node_name}' is running kubelet version {kubelet_version}. Older versions may have known CVEs and missing security features.",
                    "resource": node_name,
                    "resource_kind": "Node",
                    "namespace": "",
                    "recommendation": "Upgrade the node to a supported Kubernetes version.",
                }
            )

        # Check if node is NotReady
        conditions = node.status.conditions or []
        for condition in conditions:
            if condition.type == "Ready" and condition.status != "True":
                findings.append(
                    {
                        "id": f"node-not-ready-{node_name}",
                        "severity": "high",
                        "category": "Node Health",
                        "title": "Node is NotReady",
                        "description": f"Node '{node_name}' is in NotReady state. Reason: {condition.reason or 'Unknown'}.",
                        "resource": node_name,
                        "resource_kind": "Node",
                        "namespace": "",
                        "recommendation": "Investigate node health. Check kubelet logs and system resources.",
                    }
                )

    return findings


def check_default_namespace_usage(v1):
    """Check for resources deployed in the default namespace."""
    findings = []

    try:
        pods = v1.list_namespaced_pod("default").items
    except Exception as e:
        logger.error(f"Failed to list default namespace pods: {e}")
        return findings

    if len(pods) > 0:
        pod_names = [p.metadata.name for p in pods[:5]]
        more = f" (and {len(pods) - 5} more)" if len(pods) > 5 else ""
        findings.append(
            {
                "id": "default-namespace-usage",
                "severity": "low",
                "category": "Best Practices",
                "title": "Resources in default namespace",
                "description": f"Found {len(pods)} pod(s) in the 'default' namespace: {', '.join(pod_names)}{more}. Using the default namespace makes RBAC management harder and reduces isolation.",
                "resource": "default",
                "resource_kind": "Namespace",
                "namespace": "default",
                "recommendation": "Deploy workloads in dedicated namespaces with appropriate RBAC policies.",
            }
        )

    return findings


def check_service_account_tokens(v1):
    """Check for pods mounting default service account tokens."""
    findings = []

    try:
        pods = v1.list_pod_for_all_namespaces().items
    except Exception as e:
        logger.error(f"Failed to list pods: {e}")
        return findings

    for pod in pods:
        spec = pod.spec
        if not spec:
            continue

        automount = spec.automount_service_account_token
        if automount is not False:
            # Check if the pod actually has a service account
            sa_name = spec.service_account_name or "default"
            if sa_name == "default":
                ns = pod.metadata.namespace
                findings.append(
                    {
                        "id": f"sa-default-{ns}-{pod.metadata.name}",
                        "severity": "low",
                        "category": "Service Account",
                        "title": "Pod using default service account",
                        "description": f"Pod '{pod.metadata.name}' in namespace '{ns}' uses the default service account with auto-mounted token. This may grant unnecessary API access.",
                        "resource": f"{ns}/{pod.metadata.name}",
                        "resource_kind": "Pod",
                        "namespace": ns,
                        "recommendation": "Create a dedicated service account with minimal permissions and set automountServiceAccountToken: false if not needed.",
                    }
                )

    # Deduplicate - limit to avoid excessive findings
    return findings[:20]


@router.get("/scan")
def scan_cluster(
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """
    Run a comprehensive security scan on the cluster.

    Returns:
      {
        "score": 85,
        "total_findings": 12,
        "summary": { "critical": 1, "high": 2, "medium": 5, "low": 3, "info": 1 },
        "findings": [...],
        "scan_time": "2026-03-30T10:00:00Z"
      }
    """
    try:
        k8s, namespace = get_k8s_context(request)
        v1 = k8s.CoreV1Api()
        apps_v1 = k8s.AppsV1Api()

        # Get networking API
        try:
            from kubernetes.client import NetworkingV1Api

            networking_v1 = NetworkingV1Api(k8s.ApiClient())
        except Exception:
            networking_v1 = None

        # Get RBAC API
        try:
            from kubernetes.client import RbacAuthorizationV1Api

            rbac_api = RbacAuthorizationV1Api(k8s.ApiClient())
        except Exception:
            rbac_api = None

        # Get Policy API for PDBs
        try:
            from kubernetes.client import PolicyV1Api

            policy_v1 = PolicyV1Api(k8s.ApiClient())
        except Exception:
            policy_v1 = None

        all_findings = []

        # Run all checks
        all_findings.extend(check_pod_security(v1, namespace))

        if networking_v1:
            all_findings.extend(
                check_service_network_policies(v1, networking_v1, namespace)
            )

        if rbac_api:
            all_findings.extend(check_rbac_security(rbac_api, None))

        all_findings.extend(check_image_trust(v1, namespace))

        if policy_v1:
            all_findings.extend(check_pdb_coverage(apps_v1, policy_v1, namespace))

        # Only check node versions when scanning all namespaces
        if namespace == "_all":
            all_findings.extend(check_node_versions(v1))

        all_findings.extend(check_default_namespace_usage(v1))
        all_findings.extend(check_service_account_tokens(v1))

        # Deduplicate findings by ID
        seen_ids = set()
        unique_findings = []
        for f in all_findings:
            if f["id"] not in seen_ids:
                seen_ids.add(f["id"])
                unique_findings.append(f)

        # Calculate score
        total_penalty = sum(severity_weight(f["severity"]) for f in unique_findings)
        max_penalty = max(total_penalty, 1)  # Avoid division by zero
        score = max(0, min(100, 100 - int((total_penalty / max(max_penalty, 1)) * 50)))

        # Better scoring: base on finding count and severity
        critical_count = sum(1 for f in unique_findings if f["severity"] == "critical")
        high_count = sum(1 for f in unique_findings if f["severity"] == "high")
        medium_count = sum(1 for f in unique_findings if f["severity"] == "medium")
        low_count = sum(1 for f in unique_findings if f["severity"] == "low")
        info_count = sum(1 for f in unique_findings if f["severity"] == "info")

        # Score calculation: start at 100, deduct per finding
        score = 100
        score -= critical_count * 15
        score -= high_count * 8
        score -= medium_count * 3
        score -= low_count * 1
        score -= info_count * 0
        score = max(0, min(100, score))

        # Sort findings by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        unique_findings.sort(key=lambda f: severity_order.get(f["severity"], 5))

        return {
            "score": score,
            "total_findings": len(unique_findings),
            "summary": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "info": info_count,
            },
            "findings": unique_findings,
            "scan_time": datetime.now(timezone.utc).isoformat(),
            "namespace": namespace,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running security scan: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to run security scan: {str(e)}")
