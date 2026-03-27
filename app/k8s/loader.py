from kubernetes import config, client
from kubernetes.client import ApiClient
import yaml
import logging

logger = logging.getLogger(__name__)


def load_k8s_client(kubeconfig_path: str | None):
    """Load Kubernetes client configuration.

    If a `kubeconfig_path` is provided, attempt to load it. Otherwise try
    in-cluster configuration, then fall back to default kubeconfig.
    Returns the kubernetes client module for backward compatibility.
    """
    try:
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            # Try in-cluster first (when running inside k8s)
            config.load_incluster_config()
    except Exception as e:
        logger.warning(f"Failed to load kubeconfig: {e}. Falling back to default.")
        try:
            config.load_kube_config()
        except Exception as fallback_err:
            logger.error(f"Failed to load default kubeconfig: {fallback_err}")
            raise RuntimeError(
                "Could not load any Kubernetes configuration"
            ) from fallback_err

    return client


def get_k8s_config(kubeconfig_path: str | None = None):
    """Get Kubernetes API configuration (host, token) for direct HTTP calls.

    Returns a dict with:
    - host: API server URL
    - token: auth token (if available)
    - api_client: ApiClient instance
    """
    try:
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()
    except Exception as e:
        logger.warning(f"Failed to load kubeconfig: {e}. Falling back to default.")
        try:
            config.load_kube_config()
        except Exception as fallback_err:
            logger.error(f"Failed to load default kubeconfig: {fallback_err}")
            raise RuntimeError(
                "Could not load any Kubernetes configuration"
            ) from fallback_err

    api_client = ApiClient()

    host = None
    token = None

    # Get host from api_client configuration
    if hasattr(api_client, "configuration") and api_client.configuration:
        host = getattr(api_client.configuration, "host", None)
        logger.info(f"API host from configuration: {host}")

        # Try to get token from configuration
        config_obj = api_client.configuration
        token = getattr(config_obj, "token", None)
        if token:
            logger.info("Token extracted from api_client configuration")

    # Fallback: parse kubeconfig file directly
    if not token and kubeconfig_path:
        try:
            with open(kubeconfig_path, "r") as f:
                kubeconfig = yaml.safe_load(f)

            # Get server from cluster
            cluster = (
                kubeconfig.get("clusters", [])[0] if kubeconfig.get("clusters") else {}
            )
            server = cluster.get("cluster", {}).get("server", "")
            if server and not host:
                host = server
                logger.info(f"API host from kubeconfig: {host}")

            # Get token from user credentials - try multiple locations
            users = kubeconfig.get("users", [])
            if users:
                user = users[0]
                user_cfg = user.get("user", {})

                # Direct token
                token = user_cfg.get("token")
                if token:
                    logger.info("Token extracted from kubeconfig user.token")

                # Token from token-file
                if not token:
                    token_file = user_cfg.get("token-file")
                    if token_file:
                        try:
                            with open(token_file, "r") as tf:
                                token = tf.read().strip()
                            logger.info("Token extracted from token-file")
                        except Exception as e:
                            logger.warning(f"Failed to read token file: {e}")

                # Exec-based token
                if not token:
                    exec_config = user_cfg.get("exec")
                    if exec_config:
                        logger.info(
                            "Exec config found for token - using ApiClient auth"
                        )
        except Exception as e:
            logger.warning(f"Failed to parse kubeconfig file: {e}")

    logger.info(f"Token available: {token is not None}")
    return {
        "host": host,
        "token": token,
        "api_client": api_client,
    }
