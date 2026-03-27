import logging

logger = logging.getLogger(__name__)


def discover_resources(api_client, namespace=None):
    """Discover Kubernetes resources using the provided API client."""
    v1 = api_client.CoreV1Api()
    apps = api_client.AppsV1Api()
    networking = api_client.NetworkingV1Api()
    crd = api_client.ApiextensionsV1Api()

    # gather storage-related resources
    try:
        pvcs = v1.list_namespaced_persistent_volume_claim(namespace).items if namespace else []
    except Exception as e:
        logger.warning(f"Failed to list PVCs: {e}")
        pvcs = []

    try:
        pvs = v1.list_persistent_volume().items
    except Exception as e:
        logger.warning(f"Failed to list PVs: {e}")
        pvs = []

    try:
        storage = api_client.StorageV1Api()
        scs = storage.list_storage_class().items
    except Exception as e:
        logger.warning(f"Failed to list StorageClasses: {e}")
        scs = []

    # gather rbac-related resources
    try:
        rbac = api_client.RbacAuthorizationV1Api()
        roles = rbac.list_namespaced_role(namespace).items if namespace else rbac.list_role_for_all_namespaces().items
        rolebindings = rbac.list_namespaced_role_binding(namespace).items if namespace else rbac.list_role_binding_for_all_namespaces().items
        clusterroles = rbac.list_cluster_role().items
        clusterrolebindings = rbac.list_cluster_role_binding().items
    except Exception as e:
        logger.warning(f"Failed to list RBAC resources: {e}")
        roles = []
        rolebindings = []
        clusterroles = []
        clusterrolebindings = []

    # service accounts
    try:
        sas = v1.list_namespaced_service_account(namespace).items if namespace else []
    except Exception as e:
        logger.warning(f"Failed to list ServiceAccounts: {e}")
        sas = []

    return {
        "pods": v1.list_namespaced_pod(namespace).items if namespace else [],
        "services": v1.list_namespaced_service(namespace).items if namespace else [],
        "configmaps": v1.list_namespaced_config_map(namespace).items if namespace else [],
        "secrets": v1.list_namespaced_secret(namespace).items if namespace else [],
        "ingresses": networking.list_namespaced_ingress(namespace).items if namespace else [],
        "deployments": apps.list_namespaced_deployment(namespace).items if namespace else [],
        "statefulsets": apps.list_stateful_set_for_all_namespaces().items if not namespace else apps.list_namespaced_stateful_set(namespace).items,
        "crds": crd.list_custom_resource_definition().items,
        "pv": pvs,
        "pvc": pvcs,
        "storageclasses": scs,
        "roles": roles,
        "rolebindings": rolebindings,
        "clusterroles": clusterroles,
        "clusterrolebindings": clusterrolebindings,
        "serviceaccounts": sas,
    }