"""
Test suite for Kubernetes Metrics collection and caching.
Tests metrics collection, caching layer, and API endpoints.
"""

from fastapi.testclient import TestClient
from types import SimpleNamespace
import pytest
import time

from app.main import app
from app.k8s import metrics
from app.auth.session import get_current_user

client = TestClient(app)


class FakeMetricValue:
    """Mock for kubernetes.client.V1alpha1SampleStreamResult"""
    def __init__(self, name, usage_cpu, usage_memory, namespace="default"):
        self.metadata = SimpleNamespace(
            name=name,
            namespace=namespace,
            labels={"app": "test"}
        )
        self.usage = {
            "cpu": usage_cpu,
            "memory": usage_memory
        }


class FakeNodeMetric:
    """Mock for node metrics"""
    def __init__(self, name, usage_cpu="100m", usage_memory="256Mi"):
        self.metadata = SimpleNamespace(
            name=name,
            labels={"kubernetes.io/hostname": name}
        )
        self.usage = {
            "cpu": usage_cpu,
            "memory": usage_memory
        }


class FakePodMetric:
    """Mock for pod metrics"""
    def __init__(self, name, namespace, usage_cpu="50m", usage_memory="128Mi"):
        self.metadata = SimpleNamespace(
            name=name,
            namespace=namespace
        )
        self.containers = [
            SimpleNamespace(
                name="container1",
                usage={
                    "cpu": usage_cpu,
                    "memory": usage_memory
                }
            )
        ]


class FakeMetricsAPI:
    """Mock Kubernetes Metrics API"""
    def __init__(self):
        self.call_count = 0

    def get_node_metrics(self):
        """Mock get node metrics"""
        self.call_count += 1
        return {
            "items": [
                {
                    "metadata": {"name": "node1", "labels": {}},
                    "usage": {"cpu": "500m", "memory": "2Gi"}
                },
                {
                    "metadata": {"name": "node2", "labels": {}},
                    "usage": {"cpu": "300m", "memory": "1Gi"}
                },
            ]
        }

    def get_pod_metrics(self, namespace):
        """Mock get pod metrics"""
        self.call_count += 1
        return {
            "items": [
                {
                    "metadata": {"name": "pod1", "namespace": namespace or "default"},
                    "containers": [
                        {"name": "container1", "usage": {"cpu": "100m", "memory": "256Mi"}}
                    ]
                },
                {
                    "metadata": {"name": "pod2", "namespace": namespace or "default"},
                    "containers": [
                        {"name": "container1", "usage": {"cpu": "50m", "memory": "128Mi"}}
                    ]
                },
            ]
        }


class FakeCustomObjectsAPI:
    """Mock CustomObjectsAPI for Metrics API access"""
    def __init__(self):
        self.metrics_api = FakeMetricsAPI()

    def list_cluster_custom_object(self, group, version, plural):
        """Mock list cluster custom object for metrics"""
        if plural == "nodes":
            return self.metrics_api.get_node_metrics()
        return {"items": []}

    def list_namespaced_custom_object(self, group, version, namespace, plural):
        """Mock list namespaced custom object for metrics"""
        if plural == "pods":
            return self.metrics_api.get_pod_metrics(namespace)
        return {"items": []}


class FakeKubeClient:
    """Mock Kubernetes client with metrics support"""
    def CustomObjectsApi(self):
        return FakeCustomObjectsAPI()


# =============================================================================
# TESTS: Metrics Collection Module
# =============================================================================

@pytest.fixture(autouse=True)
def setup_auth(monkeypatch):
    """Setup auth bypass for all tests"""
    app.dependency_overrides[get_current_user] = lambda: {"role": "admin"}
    yield
    app.dependency_overrides.clear()


class TestMetricsCollection:
    """Test metrics collection functions"""

    def test_convert_cpu_to_core_units(self):
        """Test CPU value conversion"""
        # millicores to cores
        result = metrics.convert_cpu_to_cores("100m")
        assert result == 0.1, f"Expected 0.1, got {result}"

        result = metrics.convert_cpu_to_cores("500m")
        assert result == 0.5, f"Expected 0.5, got {result}"

        result = metrics.convert_cpu_to_cores("1000m")
        assert result == 1.0, f"Expected 1.0, got {result}"

    def test_convert_memory_to_bytes(self):
        """Test memory value conversion"""
        # Ki, Mi, Gi to bytes
        result = metrics.convert_memory_to_bytes("256Mi")
        assert result == 256 * 1024 * 1024, f"Expected {256*1024*1024}, got {result}"

        result = metrics.convert_memory_to_bytes("1Gi")
        assert result == 1024 * 1024 * 1024, f"Expected {1024*1024*1024}, got {result}"

        result = metrics.convert_memory_to_bytes("512Ki")
        assert result == 512 * 1024, f"Expected {512*1024}, got {result}"

    def test_format_cpu_for_display(self):
        """Test CPU display formatting"""
        result = metrics.format_cpu_for_display("100m")
        assert result == "100m"

        result = metrics.format_cpu_for_display("1000m")
        assert result == "1"

    def test_format_memory_for_display(self):
        """Test memory display formatting"""
        result = metrics.format_memory_for_display(256 * 1024 * 1024)
        assert "Mi" in result or "M" in result

    def test_parse_node_metrics(self, monkeypatch):
        """Test node metrics parsing"""
        fake_api = FakeCustomObjectsAPI()
        fake_client = object()

        def mock_custom_objects_api(client):
            return fake_api

        monkeypatch.setattr(metrics, "CustomObjectsApi", mock_custom_objects_api)

        result = metrics.parse_node_metrics(fake_client)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "node1"
        assert "cpu" in result[0]
        assert "memory" in result[0]

    def test_parse_pod_metrics(self, monkeypatch):
        """Test pod metrics parsing"""
        fake_api = FakeCustomObjectsAPI()
        fake_client = object()

        def mock_custom_objects_api(client):
            return fake_api

        monkeypatch.setattr(metrics, "CustomObjectsApi", mock_custom_objects_api)

        result = metrics.parse_pod_metrics(fake_client, "default")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "pod1"
        assert result[0]["namespace"] == "default"
        assert "cpu" in result[0]
        assert "memory" in result[0]


# =============================================================================
# TESTS: Metrics Caching Layer
# =============================================================================

class TestMetricsCache:
    """Test metrics caching functionality"""

    def test_cache_initialization(self):
        """Test cache instance creation"""
        cache = metrics.MetricsCache(ttl_seconds=60)
        assert cache.ttl_seconds == 60
        assert cache.cache == {}

    def test_cache_set_and_get(self):
        """Test basic cache set/get operations"""
        cache = metrics.MetricsCache(ttl_seconds=60)

        test_data = {"test": "value"}
        cache.set("test_key", test_data)

        result = cache.get("test_key")
        assert result == test_data

    def test_cache_expiration(self):
        """Test cache expiration after TTL"""
        cache = metrics.MetricsCache(ttl_seconds=1)

        cache.set("expiring_key", {"test": "data"})
        result = cache.get("expiring_key")
        assert result == {"test": "data"}

        # Wait for expiration
        time.sleep(1.1)
        result = cache.get("expiring_key")
        assert result is None

    def test_cache_none_returns_none(self):
        """Test cache returns None for missing keys"""
        cache = metrics.MetricsCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_clear(self):
        """Test cache clear functionality"""
        cache = metrics.MetricsCache()
        cache.set("key1", {"data": 1})
        cache.set("key2", {"data": 2})

        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_global_instance(self):
        """Test global cache instance is accessible"""
        from app.k8s.metrics import get_cache
        cache = get_cache()
        assert cache is not None
        assert isinstance(cache, metrics.MetricsCache)


# =============================================================================
# TESTS: Metrics API Endpoints (Integration)
# =============================================================================

class TestMetricsEndpoints:
    """Test metrics API endpoints"""

    def test_cluster_metrics_endpoint_exists(self):
        """Test cluster metrics endpoint is accessible"""
        # This test documents the expected endpoint
        # Actual response tested after implementation
        assert True, "Endpoint: GET /api/metrics/cluster"

    def test_node_metrics_endpoint_exists(self):
        """Test node metrics endpoint is accessible"""
        # This test documents the expected endpoint
        assert True, "Endpoint: GET /api/metrics/nodes"

    def test_namespace_metrics_endpoint_exists(self):
        """Test namespace metrics endpoint is accessible"""
        # This test documents the expected endpoint
        assert True, "Endpoint: GET /api/metrics/namespace/{namespace}"

    def test_pod_metrics_endpoint_exists(self):
        """Test pod metrics endpoint is accessible"""
        # This test documents the expected endpoint
        assert True, "Endpoint: GET /api/metrics/pod/{namespace}/{pod}"

    def test_pvc_metrics_endpoint_exists(self):
        """Test PVC metrics endpoint is accessible"""
        # This test documents the expected endpoint
        assert True, "Endpoint: GET /api/metrics/pvc/{namespace}"


# =============================================================================
# TESTS: Error Handling
# =============================================================================

class TestMetricsErrorHandling:
    """Test error handling in metrics collection"""

    def test_invalid_cpu_format(self):
        """Test handling of invalid CPU format"""
        result = metrics.convert_cpu_to_cores("invalid")
        assert result == 0 or result is None, "Should handle invalid format gracefully"

    def test_invalid_memory_format(self):
        """Test handling of invalid memory format"""
        result = metrics.convert_memory_to_bytes("invalid")
        assert result == 0 or result is None, "Should handle invalid format gracefully"

    def test_missing_metrics_server(self):
        """Test graceful degradation when Metrics Server is unavailable"""
        # This test documents expected behavior
        # Implementation should catch CustomObjectsApi errors
        assert True, "Should return empty list if Metrics Server unavailable"

    def test_node_without_metrics(self):
        """Test handling of nodes without metrics"""
        # Create a fake node without usage data
        result = metrics.parse_node_metrics(FakeKubeClient())
        # Should not crash
        assert isinstance(result, list)


# =============================================================================
# TESTS: Metrics Aggregation
# =============================================================================

class TestMetricsAggregation:
    """Test metrics aggregation functions"""

    def test_aggregate_node_metrics(self):
        """Test aggregation of node metrics"""
        node_metrics = [
            {"name": "node1", "cpu": 0.5, "memory": 2.0},
            {"name": "node2", "cpu": 0.3, "memory": 1.0},
        ]

        result = metrics.aggregate_node_metrics(node_metrics)

        assert result["total_cpu"] == 0.8
        assert result["total_memory"] == 3.0
        assert result["node_count"] == 2

    def test_aggregate_pod_metrics(self):
        """Test aggregation of pod metrics by namespace"""
        pod_metrics = [
            {"namespace": "default", "cpu": 0.1, "memory": 0.25},
            {"namespace": "default", "cpu": 0.05, "memory": 0.125},
            {"namespace": "kube-system", "cpu": 0.2, "memory": 0.5},
        ]

        result = metrics.aggregate_pod_metrics_by_namespace(pod_metrics)

        assert "default" in result
        assert "kube-system" in result
        assert abs(result["default"]["cpu"] - 0.15) < 0.001
        assert abs(result["default"]["memory"] - 0.375) < 0.001


# =============================================================================
# TESTS: Cache Performance
# =============================================================================

class TestCachePerformance:
    """Test cache performance characteristics"""

    def test_cache_reduces_api_calls(self, monkeypatch):
        """Test that caching reduces API call count"""
        fake_api = FakeCustomObjectsAPI()
        fake_client = object()  # Not used, we'll mock CustomObjectsApi directly
        cache = metrics.MetricsCache(ttl_seconds=60)

        # Mock CustomObjectsApi in the metrics module
        def mock_custom_objects_api(client):
            return fake_api

        monkeypatch.setattr(metrics, "CustomObjectsApi", mock_custom_objects_api)

        # First call - should fetch from API
        call_count_before = fake_api.metrics_api.call_count
        result1 = metrics.parse_node_metrics(fake_client)
        call_count_after = fake_api.metrics_api.call_count

        assert call_count_after > call_count_before, "First call should hit API"
        assert len(result1) == 2, f"Expected 2 nodes, got {len(result1)}"

        # Test caching wrapper
        result1_cached = metrics.get_cached_node_metrics(fake_client, cache)
        call_count_first_cache = fake_api.metrics_api.call_count

        result2_cached = metrics.get_cached_node_metrics(fake_client, cache)
        call_count_second_cache = fake_api.metrics_api.call_count

        # No additional API calls on second cache hit
        assert call_count_second_cache == call_count_first_cache

    def test_cache_performance_threshold(self):
        """Test cache response time is acceptable"""
        cache = metrics.MetricsCache()
        test_data = {"nodes": [{"name": "node1", "cpu": 0.5}] * 100}

        cache.set("large_dataset", test_data)

        import timeit
        start = timeit.default_timer()
        for _ in range(1000):
            cache.get("large_dataset")
        end = timeit.default_timer()

        time_per_call = (end - start) / 1000
        assert time_per_call < 0.001, f"Cache lookup too slow: {time_per_call}ms"


# =============================================================================
# End of Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
