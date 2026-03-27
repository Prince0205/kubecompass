"""
Kubernetes Metrics Collection Module

Provides functions to collect and parse Kubernetes resource metrics (CPU, Memory)
from the Kubernetes Metrics API. Supports optional caching to reduce API calls.

This module handles:
- Node metrics collection
- Pod metrics collection
- CPU/Memory unit conversions
- Metrics aggregation
- Graceful degradation when Metrics Server is unavailable
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re
import warnings
from kubernetes.client.rest import ApiException
from kubernetes.client import CustomObjectsApi


# =============================================================================
# UNIT CONVERSION FUNCTIONS
# =============================================================================


def convert_cpu_to_cores(cpu_str: str) -> float:
    """
    Convert Kubernetes CPU value to cores (numeric).

    Args:
        cpu_str: CPU value like "100m" (millicores), "1" (cores), or "1500m"

    Returns:
        CPU value in cores as float. Returns 0 on invalid input.

    Examples:
        "100m" -> 0.1
        "500m" -> 0.5
        "1" -> 1.0
        "2" -> 2.0
    """
    if not cpu_str:
        return 0.0

    try:
        # Remove whitespace
        cpu_str = cpu_str.strip()

        # If ends with 'm' (millicores), divide by 1000
        if cpu_str.endswith("m"):
            return float(cpu_str[:-1]) / 1000.0

        # Otherwise treat as cores
        return float(cpu_str)

    except (ValueError, IndexError):
        return 0.0


def convert_memory_to_bytes(memory_str: str) -> int:
    """
    Convert Kubernetes memory value to bytes.

    Args:
        memory_str: Memory value like "256Mi", "1Gi", "512Ki", "1000", etc.

    Returns:
        Memory in bytes as int. Returns 0 on invalid input.

    Examples:
        "256Mi" -> 268435456 (256 * 1024 * 1024)
        "1Gi" -> 1073741824 (1 * 1024 * 1024 * 1024)
        "512Ki" -> 524288 (512 * 1024)
    """
    if not memory_str:
        return 0

    try:
        memory_str = memory_str.strip()

        # Define multipliers for each unit (case-sensitive)
        units = {
            "Ki": 1024,
            "Mi": 1024 * 1024,
            "Gi": 1024 * 1024 * 1024,
            "Ti": 1024 * 1024 * 1024 * 1024,
            "K": 1000,
            "M": 1000 * 1000,
            "G": 1000 * 1000 * 1000,
            "T": 1000 * 1000 * 1000 * 1000,
        }

        # Check for known units (case-sensitive)
        for unit, multiplier in units.items():
            if memory_str.endswith(unit):
                value = float(memory_str[: -len(unit)])
                return int(value * multiplier)

        # If no unit, treat as bytes
        return int(float(memory_str))

    except (ValueError, TypeError):
        return 0


def format_cpu_for_display(cpu_str: str) -> str:
    """
    Format CPU value for display to users.

    Args:
        cpu_str: CPU value like "100m" or "1000m"

    Returns:
        Formatted string for display. Values >= 1000m are shown in cores,
        values < 1000m are shown in millicores.

    Examples:
        "100m" -> "100m"
        "1000m" -> "1"
        "1500m" -> "1.5"
        "2000m" -> "2"
        "500m" -> "500m"
    """
    if not cpu_str:
        return "0m"

    try:
        cpu_str = cpu_str.strip()

        # If ends with 'm', convert to cores for display if >= 1000m
        if cpu_str.endswith("m"):
            value = float(cpu_str[:-1])
            if value >= 1000:
                # Show in cores, remove trailing zeros
                cores_value = value / 1000.0
                if cores_value.is_integer():
                    return str(int(cores_value))
                else:
                    # Remove trailing zeros for cleaner display
                    return str(cores_value).rstrip("0").rstrip(".")
            return cpu_str

        return cpu_str

    except (ValueError, IndexError):
        return cpu_str


def format_memory_for_display(memory_bytes: int) -> str:
    """
    Format memory value for display to users.

    Args:
        memory_bytes: Memory in bytes

    Returns:
        Formatted string like "256Mi", "1Gi", etc.

    Examples:
        268435456 (256Mi) -> "256Mi"
        1073741824 (1Gi) -> "1Gi"
    """
    if memory_bytes <= 0:
        return "0Mi"

    units = [
        ("Gi", 1024 * 1024 * 1024),
        ("Mi", 1024 * 1024),
        ("Ki", 1024),
    ]

    for unit, divisor in units:
        if memory_bytes >= divisor:
            value = memory_bytes / divisor
            # Return with 1 decimal if needed, otherwise as int
            if value % 1 < 0.1:
                return f"{int(value)}{unit}"
            else:
                return f"{value:.1f}{unit}"

    return f"{memory_bytes}B"


# =============================================================================
# METRICS PARSING FUNCTIONS
# =============================================================================


def parse_node_metrics(api_client, host=None, token=None) -> List[Dict[str, Any]]:
    """
    Fetch and parse node metrics from Kubernetes Metrics API.

    Args:
        api_client: Kubernetes ApiClient instance
        host: Optional API host URL
        token: Optional auth token

    Returns:
        List of dicts with keys: name, cpu, memory, cpu_cores, memory_bytes

    Gracefully returns empty list if Metrics Server is unavailable.
    """
    import logging
    import requests
    import urllib3

    logger = logging.getLogger(__name__)

    # Method 1: Direct HTTP call (most reliable for Python 3.14 compatibility)
    try:
        if not host:
            # Try to get host from api_client configuration
            if hasattr(api_client, "configuration") and api_client.configuration:
                host = getattr(api_client.configuration, "host", None)

        if not host:
            logger.debug(
                "No API host available for direct HTTP call, trying CustomObjectsApi"
            )
            raise RuntimeError("No host available")

        url = f"{host.rstrip('/')}/apis/metrics.k8s.io/v1beta1/nodes"
        logger.info(f"Fetching metrics from: {url}")

        # Use provided token or try to get from api_client
        auth_token = token
        if not auth_token:
            # Try to get from api_client default headers
            if hasattr(api_client, "default_headers"):
                auth_token = api_client.default_headers.get("Authorization")
                if auth_token:
                    logger.info("Got token from api_client.default_headers")

        # If still no token, try to get from api_client configuration
        if (
            not auth_token
            and hasattr(api_client, "configuration")
            and api_client.configuration
        ):
            config = api_client.configuration
            # Try multiple possible token locations in config
            if not auth_token:
                # Try direct token attribute
                auth_token = getattr(config, "token", None)
                if auth_token:
                    logger.info("Got token from api_client.configuration.token")

            if not auth_token:
                # Try access_token attribute
                auth_token = getattr(config, "access_token", None)
                if auth_token:
                    logger.info("Got token from api_client.configuration.access_token")

            if not auth_token:
                # Try api_key dict (common in k8s client)
                api_key = getattr(config, "api_key", {})
                if isinstance(api_key, dict):
                    auth_token = api_key.get("authorization")
                    if auth_token:
                        logger.info(
                            "Got token from api_client.configuration.api_key['authorization']"
                        )

            if not auth_token:
                # Try api_key_prefix dict
                api_key_prefix = getattr(config, "api_key_prefix", {})
                if isinstance(api_key_prefix, dict):
                    prefix = api_key_prefix.get("authorization")
                    if prefix:
                        # Get the actual token from api_key
                        api_key = getattr(config, "api_key", {})
                        if isinstance(api_key, dict):
                            token_value = api_key.get("authorization")
                            if token_value:
                                auth_token = f"{prefix} {token_value}"
                                logger.info(
                                    "Got token from api_client.configuration.api_key_prefix and api_key"
                                )

        headers = {"Accept": "application/json"}
        if auth_token:
            # Ensure Bearer prefix
            if not auth_token.startswith("Bearer "):
                auth_token = f"Bearer {auth_token}"
            headers["Authorization"] = auth_token
            logger.info("Using Bearer token for authentication")
        else:
            logger.warning("No authentication token available for metrics API")

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.debug(f"Request headers: {list(headers.keys())}")
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        logger.info(f"Metrics API response status: {response.status_code}")

        if response.status_code == 200:
            metrics_data = response.json()
            items = metrics_data.get("items", [])
            logger.info(f"Successfully parsed {len(items)} node metrics")
            result = []
            for item in items:
                name = item.get("metadata", {}).get("name")
                usage = item.get("usage", {})
                cpu_raw = usage.get("cpu", "0m") if usage else "0m"
                memory_raw = usage.get("memory", "0Mi") if usage else "0Mi"

                # Convert to proper formats
                memory_bytes = convert_memory_to_bytes(memory_raw)
                cpu_cores = convert_cpu_to_cores(cpu_raw)

                result.append(
                    {
                        "name": name,
                        "cpu": format_cpu_for_display(cpu_raw),
                        "memory": format_memory_for_display(memory_bytes),
                        "cpu_cores": cpu_cores,
                        "memory_bytes": memory_bytes,
                    }
                )
            logger.info(f"HTTP direct parsed {len(result)} node metrics")
            return result
        else:
            error_msg = f"Metrics API returned {response.status_code}"
            try:
                error_detail = response.json()
                logger.error(f"{error_msg}: {error_detail}")
            except:
                logger.error(f"{error_msg}: {response.text[:200]}")
            raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"HTTP direct failed: {type(e).__name__}: {e}", exc_info=True)

    # Method 2: Try CustomObjectsApi
    try:
        logger.info("Attempting to fetch metrics via CustomObjectsApi")
        api = CustomObjectsApi(api_client)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metrics_list = api.list_cluster_custom_object(
                group="metrics.k8s.io", version="v1beta1", plural="nodes"
            )

        items = metrics_list.get("items", []) if isinstance(metrics_list, dict) else []
        logger.info(f"CustomObjectsApi returned {len(items)} items")
        if items:
            logger.info(f"CustomObjectsApi returned {len(items)} node metrics")
            result = []
            for idx, item in enumerate(items):
                try:
                    name = item.get("metadata", {}).get("name")
                    usage = item.get("usage", {})
                    cpu_raw = usage.get("cpu", "0m") if usage else "0m"
                    memory_raw = usage.get("memory", "0Mi") if usage else "0Mi"
                    logger.debug(
                        f"Item {idx}: name={name}, cpu_raw={cpu_raw}, memory_raw={memory_raw}"
                    )

                    cpu_formatted = format_cpu_for_display(cpu_raw)
                    memory_bytes = convert_memory_to_bytes(memory_raw)
                    memory_formatted = format_memory_for_display(memory_bytes)

                    result.append(
                        {
                            "name": name,
                            "cpu": cpu_formatted,
                            "memory": memory_formatted,
                            "cpu_cores": convert_cpu_to_cores(cpu_raw),
                            "memory_bytes": memory_bytes,
                        }
                    )
                except Exception as item_err:
                    logger.error(
                        f"Error processing item {idx}: {type(item_err).__name__}: {item_err}",
                        exc_info=True,
                    )
                    raise

            logger.info(f"CustomObjectsApi parsed {len(result)} node metrics")
            return result
        else:
            logger.warning("CustomObjectsApi returned no items")
    except Exception as e:
        logger.error(f"CustomObjectsApi failed: {type(e).__name__}: {e}", exc_info=True)

    return []


def _parse_node_metrics_fallback(api_client) -> List[Dict[str, Any]]:
    """Fallback method using direct HTTP requests"""
    import logging
    import requests
    import urllib3

    logger = logging.getLogger(__name__)

    try:
        # Get the configuration from api_client
        config = None
        if hasattr(api_client, "configuration"):
            config = api_client.configuration
        elif hasattr(api_client, "_configuration"):
            config = api_client._configuration

        # Get host - try multiple approaches
        host = None
        if config:
            # Try different attribute names
            for attr in ["host", "host_url", "base_url", "server_address"]:
                if hasattr(config, attr):
                    host = getattr(config, attr)
                    break

        if not host:
            # Get from api_client itself
            for attr in ["host", "base_url"]:
                if hasattr(api_client, attr):
                    host = getattr(api_client, attr)
                    break

        # Get token - try from configuration
        token = None
        if config:
            # Try to get token from configuration
            for attr in ["api_key", "api_key_prefix", "token"]:
                if hasattr(config, attr):
                    val = getattr(config, attr)
                    if isinstance(val, dict) and "Authorization" in val:
                        token = val["Authorization"]
                    elif isinstance(val, str) and val:
                        token = f"Bearer {val}"
                        break

        if not token:
            # Try from default headers
            if hasattr(api_client, "default_headers"):
                for key, val in api_client.default_headers.items():
                    if key.lower() == "authorization":
                        token = val
                        break

        if not host:
            logger.error("Could not determine API host")
            return []

        # Make the request
        url = f"{host.rstrip('/')}/apis/metrics.k8s.io/v1beta1/nodes"
        headers = {}
        if token:
            headers["Authorization"] = token
        headers["Accept"] = "application/json"

        # Disable SSL warnings for internal K8s calls
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        response = requests.get(url, headers=headers, verify=False, timeout=15)

        if response.status_code != 200:
            logger.error(
                f"Metrics API returned {response.status_code}: {response.text[:200]}"
            )
            return []

        metrics_data = response.json()
        items = metrics_data.get("items", [])
        result = []

        for item in items:
            name = item.get("metadata", {}).get("name")
            usage = item.get("usage", {})

            cpu_raw = usage.get("cpu", "0m") if usage else "0m"
            memory_raw = usage.get("memory", "0Mi") if usage else "0Mi"

            # Convert memory to bytes for display formatting
            memory_bytes = convert_memory_to_bytes(memory_raw)

            result.append(
                {
                    "name": name,
                    "cpu": format_cpu_for_display(cpu_raw),
                    "memory": format_memory_for_display(memory_bytes),
                    "cpu_cores": convert_cpu_to_cores(cpu_raw),
                    "memory_bytes": memory_bytes,
                }
            )

        logger.info(f"HTTP fallback parsed {len(result)} node metrics")
        return result

    except Exception as e:
        logger.error(f"HTTP fallback failed: {type(e).__name__}: {e}")
        return []


def parse_pod_metrics(api_client, namespace: str) -> List[Dict[str, Any]]:
    """
    Fetch and parse pod metrics from Kubernetes Metrics API.

    Args:
        api_client: Kubernetes ApiClient instance
        namespace: Kubernetes namespace

    Returns:
        List of dicts with keys: name, namespace, cpu, memory, cpu_cores, memory_bytes

    Gracefully returns empty list if Metrics Server is unavailable.
    """
    try:
        api = CustomObjectsApi(api_client)
        metrics_list = api.list_namespaced_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace=namespace,
            plural="pods",
        )

        result = []
        for item in metrics_list.get("items", []):
            name = item.get("metadata", {}).get("name")
            ns = item.get("metadata", {}).get("namespace", namespace)

            # Sum metrics across all containers in the pod
            total_cpu_cores = 0
            total_memory_bytes = 0

            for container in item.get("containers", []):
                usage = container.get("usage", {})
                cpu_raw = usage.get("cpu", "0m")
                memory_raw = usage.get("memory", "0Mi")

                total_cpu_cores += convert_cpu_to_cores(cpu_raw)
                total_memory_bytes += convert_memory_to_bytes(memory_raw)

            result.append(
                {
                    "name": name,
                    "namespace": ns,
                    "cpu": format_cpu_for_display(f"{int(total_cpu_cores * 1000)}m"),
                    "memory": format_memory_for_display(total_memory_bytes),
                    "cpu_cores": total_cpu_cores,
                    "memory_bytes": total_memory_bytes,
                }
            )

        return result

    except (ApiException, Exception) as e:
        # Metrics Server likely not installed
        return []


# =============================================================================
# METRICS AGGREGATION FUNCTIONS
# =============================================================================


def aggregate_node_metrics(node_metrics: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregate node metrics across all nodes.

    Args:
        node_metrics: List of node metric dicts

    Returns:
        Dict with: total_cpu (cores), total_memory (bytes), node_count
    """
    total_cpu = sum(m.get("cpu_cores", m.get("cpu", 0)) for m in node_metrics)
    total_memory = sum(m.get("memory_bytes", m.get("memory", 0)) for m in node_metrics)

    return {
        "total_cpu": total_cpu,
        "total_memory": total_memory,
        "node_count": len(node_metrics),
        "average_cpu": total_cpu / len(node_metrics) if node_metrics else 0,
        "average_memory": total_memory / len(node_metrics) if node_metrics else 0,
    }


def aggregate_pod_metrics_by_namespace(
    pod_metrics: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """
    Aggregate pod metrics grouped by namespace.

    Args:
        pod_metrics: List of pod metric dicts

    Returns:
        Dict keyed by namespace with aggregated metrics
    """
    aggregated = {}

    for pod in pod_metrics:
        namespace = pod.get("namespace", "default")

        if namespace not in aggregated:
            aggregated[namespace] = {
                "cpu": 0,
                "memory": 0,
                "pod_count": 0,
            }

        aggregated[namespace]["cpu"] += pod.get("cpu_cores", pod.get("cpu", 0))
        aggregated[namespace]["memory"] += pod.get("memory_bytes", pod.get("memory", 0))
        aggregated[namespace]["pod_count"] += 1

    return aggregated


# =============================================================================
# METRICS CACHING LAYER
# =============================================================================


class MetricsCache:
    """
    Simple in-memory cache for metrics with TTL (Time To Live) support.

    Purpose:
    - Reduce API calls to Kubernetes
    - Improve dashboard responsiveness
    - Allow metrics to be shared across users
    - Graceful expiration of stale data
    """

    def __init__(self, ttl_seconds: int = 60):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time to live for cached entries (default 60 seconds)
        """
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
        """
        expiry_time = datetime.now() + timedelta(seconds=self.ttl_seconds)
        self.cache[key] = (value, expiry_time)

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self.cache:
            return None

        value, expiry_time = self.cache[key]

        # Check if expired
        if datetime.now() > expiry_time:
            del self.cache[key]
            return None

        return value

    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()

    def cleanup_expired(self) -> None:
        """Remove all expired entries."""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expiry_time) in self.cache.items() if now > expiry_time
        ]
        for key in expired_keys:
            del self.cache[key]


# Global cache instance
_metrics_cache: Optional[MetricsCache] = None


def get_cache(ttl_seconds: int = 60) -> MetricsCache:
    """
    Get or create global metrics cache instance.

    Args:
        ttl_seconds: TTL for cache entries (only used on first init)

    Returns:
        Global MetricsCache instance
    """
    global _metrics_cache
    if _metrics_cache is None:
        _metrics_cache = MetricsCache(ttl_seconds=ttl_seconds)
    return _metrics_cache


# =============================================================================
# CACHED METRICS FUNCTIONS
# =============================================================================


def get_cached_node_metrics(api_client, cache: Optional[MetricsCache] = None):
    """
    Get node metrics with caching.

    Args:
        api_client: Kubernetes ApiClient
        cache: Optional MetricsCache instance. If None, cache is not used.

    Returns:
        List of node metrics
    """
    if cache is None:
        cache = get_cache()

    cache_key = "node_metrics"
    cached_result = cache.get(cache_key)

    if cached_result is not None:
        return cached_result

    # Fetch fresh metrics
    result = parse_node_metrics(api_client)
    cache.set(cache_key, result)

    return result


def get_cached_pod_metrics(
    api_client, namespace: str, cache: Optional[MetricsCache] = None
):
    """
    Get pod metrics with caching.

    Args:
        api_client: Kubernetes ApiClient
        namespace: Kubernetes namespace
        cache: Optional MetricsCache instance. If None, cache is not used.

    Returns:
        List of pod metrics
    """
    if cache is None:
        cache = get_cache()

    cache_key = f"pod_metrics:{namespace}"
    cached_result = cache.get(cache_key)

    if cached_result is not None:
        return cached_result

    # Fetch fresh metrics
    result = parse_pod_metrics(api_client, namespace)
    cache.set(cache_key, result)

    return result


# =============================================================================
# End of Module
# =============================================================================
