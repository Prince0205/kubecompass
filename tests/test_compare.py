"""
Test Multi-Cluster Compare Endpoints

Tests for the /api/compare endpoints that compare Kubernetes
resources across clusters.
"""

from fastapi.testclient import TestClient
from types import SimpleNamespace
from app.main import app
from app.auth.session import get_current_user
from app.routes import compare as compare_module

client = TestClient(app)


def setup():
    app.dependency_overrides[get_current_user] = lambda: {"role": "admin"}


def teardown():
    app.dependency_overrides.clear()


def run_test(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
    except Exception as e:
        print(f"[ERROR] {name}: {e}")


def test_resource_types_endpoint():
    """Test that resource types endpoint returns supported types."""
    setup()
    r = client.get("/api/compare/resource-types")
    teardown()
    assert r.status_code == 200, f"Expected 200 but got {r.status_code}"
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    keys = [rt["key"] for rt in data]
    assert "deployments" in keys
    assert "services" in keys
    assert "configmaps" in keys
    for rt in data:
        assert "key" in rt
        assert "kind" in rt


def test_compare_same_cluster_fails():
    """Test that comparing the same cluster returns 400."""
    setup()
    r = client.get(
        "/api/compare/resources",
        params={
            "cluster_a": "same-id",
            "cluster_b": "same-id",
            "resource_type": "deployments",
        },
    )
    teardown()
    assert r.status_code == 400, f"Expected 400 but got {r.status_code}"


def test_compare_unsupported_type_fails():
    """Test that unsupported resource type returns 400."""
    setup()
    r = client.get(
        "/api/compare/resources",
        params={
            "cluster_a": "cluster-a-id",
            "cluster_b": "cluster-b-id",
            "resource_type": "unsupported_type",
        },
    )
    teardown()
    assert r.status_code == 400, f"Expected 400 but got {r.status_code}"


def test_compare_returns_valid_structure():
    """Test that comparison returns the expected JSON structure."""
    setup()

    original_get = compare_module._get_api_client
    original_for = compare_module._get_api_for_type

    compare_module._get_api_client = lambda cid: (None, f"cluster-{cid[:4]}")
    compare_module._get_api_for_type = lambda client, rt: SimpleNamespace(
        list_namespaced_deployment=lambda ns: SimpleNamespace(items=[])
    )

    try:
        r = client.get(
            "/api/compare/resources",
            params={
                "cluster_a": "aaaa-bbbb",
                "cluster_b": "cccc-dddd",
                "resource_type": "deployments",
                "namespace": "default",
            },
        )
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}: {r.text}"
        data = r.json()

        assert "cluster_a" in data
        assert "cluster_b" in data
        assert "resource_type" in data
        assert "namespace" in data
        assert "summary" in data
        assert "comparisons" in data

        summary = data["summary"]
        assert "total" in summary
        assert "identical" in summary
        assert "drifted" in summary
        assert "only_in_a" in summary
        assert "only_in_b" in summary

    finally:
        compare_module._get_api_client = original_get
        compare_module._get_api_for_type = original_for
        teardown()


def test_compare_detects_drift():
    """Test that comparison correctly detects drift between clusters."""
    setup()

    original_get = compare_module._get_api_client
    original_for = compare_module._get_api_for_type

    class FakeDeploymentA:
        metadata = SimpleNamespace(name="nginx", namespace="default")

        def to_dict(self):
            return {
                "metadata": {"name": "nginx", "namespace": "default"},
                "spec": {"replicas": 3, "selector": {"matchLabels": {"app": "nginx"}}},
            }

    class FakeDeploymentB:
        metadata = SimpleNamespace(name="nginx", namespace="default")

        def to_dict(self):
            return {
                "metadata": {"name": "nginx", "namespace": "default"},
                "spec": {"replicas": 5, "selector": {"matchLabels": {"app": "nginx"}}},
            }

    class FakeAppsA:
        def list_namespaced_deployment(self, ns):
            return SimpleNamespace(items=[FakeDeploymentA()])

    class FakeAppsB:
        def list_namespaced_deployment(self, ns):
            return SimpleNamespace(items=[FakeDeploymentB()])

    call_count = [0]

    def fake_get_api_for(client, rt):
        call_count[0] += 1
        if call_count[0] == 1:
            return FakeAppsA()
        else:
            return FakeAppsB()

    compare_module._get_api_client = lambda cid: (None, f"cluster-{cid[:4]}")
    compare_module._get_api_for_type = fake_get_api_for

    try:
        r = client.get(
            "/api/compare/resources",
            params={
                "cluster_a": "aaaa-bbbb",
                "cluster_b": "cccc-dddd",
                "resource_type": "deployments",
                "namespace": "default",
            },
        )
        assert r.status_code == 200
        data = r.json()

        assert data["summary"]["drifted"] == 1
        assert data["summary"]["total"] == 1
        assert len(data["comparisons"]) == 1

        comp = data["comparisons"][0]
        assert comp["status"] == "drifted"
        assert comp["in_cluster_a"] is True
        assert comp["in_cluster_b"] is True
        assert len(comp["diff"]) > 0
        assert comp["resource_key"] == "default/nginx"

    finally:
        compare_module._get_api_client = original_get
        compare_module._get_api_for_type = original_for
        teardown()


def test_compare_detects_only_in_a():
    """Test that comparison detects resources only in cluster A."""
    setup()

    original_get = compare_module._get_api_client
    original_for = compare_module._get_api_for_type

    class FakeDeployment:
        metadata = SimpleNamespace(name="nginx", namespace="default")

        def to_dict(self):
            return {
                "metadata": {"name": "nginx", "namespace": "default"},
                "spec": {"replicas": 3},
            }

    class FakeAppsA:
        def list_namespaced_deployment(self, ns):
            return SimpleNamespace(items=[FakeDeployment()])

    class FakeAppsB:
        def list_namespaced_deployment(self, ns):
            return SimpleNamespace(items=[])

    call_count = [0]

    def fake_get_api_for(client, rt):
        call_count[0] += 1
        if call_count[0] == 1:
            return FakeAppsA()
        else:
            return FakeAppsB()

    compare_module._get_api_client = lambda cid: (None, f"cluster-{cid[:4]}")
    compare_module._get_api_for_type = fake_get_api_for

    try:
        r = client.get(
            "/api/compare/resources",
            params={
                "cluster_a": "aaaa-bbbb",
                "cluster_b": "cccc-dddd",
                "resource_type": "deployments",
                "namespace": "default",
            },
        )
        assert r.status_code == 200
        data = r.json()

        assert data["summary"]["only_in_a"] == 1
        assert data["summary"]["only_in_b"] == 0
        assert data["summary"]["drifted"] == 0

        comp = data["comparisons"][0]
        assert comp["status"] == "only_in_a"
        assert comp["in_cluster_a"] is True
        assert comp["in_cluster_b"] is False

    finally:
        compare_module._get_api_client = original_get
        compare_module._get_api_for_type = original_for
        teardown()


if __name__ == "__main__":
    setup()
    tests = [
        ("resource_types_endpoint", test_resource_types_endpoint),
        ("compare_same_cluster_fails", test_compare_same_cluster_fails),
        ("compare_unsupported_type_fails", test_compare_unsupported_type_fails),
        ("compare_returns_valid_structure", test_compare_returns_valid_structure),
        ("compare_detects_drift", test_compare_detects_drift),
        ("compare_detects_only_in_a", test_compare_detects_only_in_a),
    ]
    for name, fn in tests:
        run_test(name, fn)
    teardown()
