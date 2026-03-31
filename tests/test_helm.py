"""
Test Helm Manager Endpoints

Tests for the /api/helm endpoints that manage Helm releases,
repositories, and chart operations.
"""

from fastapi.testclient import TestClient
from fastapi import HTTPException
from types import SimpleNamespace
from app.main import app
from app.auth.session import get_current_user
from app.routes import helm as helm_module

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


def test_helm_list_releases_endpoint():
    """Test that releases endpoint exists and handles missing kubeconfig."""
    setup()

    original = helm_module._get_kubeconfig

    def fake_kubeconfig(req):
        raise HTTPException(400, "No active cluster selected")

    helm_module._get_kubeconfig = fake_kubeconfig

    try:
        r = client.get("/api/helm/releases")
        # Should fail because kubeconfig is not available
        assert r.status_code in (400, 500), f"Expected 400/500 but got {r.status_code}"
    finally:
        helm_module._get_kubeconfig = original
        teardown()


def test_helm_list_repos_endpoint():
    """Test that repos endpoint returns a list (possibly empty)."""
    setup()

    original_run = helm_module._run_helm
    helm_module._run_helm = lambda *a, **kw: {"data": []}

    try:
        r = client.get("/api/helm/repos")
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}"
        data = r.json()
        assert isinstance(data, list)
    finally:
        helm_module._run_helm = original_run
        teardown()


def test_helm_install_missing_fields():
    """Test that install endpoint validates required fields."""
    setup()

    original = helm_module._get_kubeconfig
    helm_module._get_kubeconfig = lambda req: "/tmp/kubeconfig"

    try:
        r = client.post("/api/helm/releases", json={})
        assert r.status_code == 400, f"Expected 400 but got {r.status_code}"
    finally:
        helm_module._get_kubeconfig = original
        teardown()


def test_helm_rollback_missing_revision():
    """Test that rollback endpoint requires revision."""
    setup()

    original = helm_module._get_kubeconfig
    helm_module._get_kubeconfig = lambda req: "/tmp/kubeconfig"

    try:
        r = client.post("/api/helm/releases/test-release/rollback", json={})
        assert r.status_code == 400, f"Expected 400 but got {r.status_code}"
    finally:
        helm_module._get_kubeconfig = original
        teardown()


def test_helm_search_endpoint():
    """Test that search endpoint returns results."""
    setup()

    original_run = helm_module._run_helm
    helm_module._run_helm = lambda *a, **kw: {
        "data": [
            {"name": "bitnami/nginx", "version": "15.0.0", "description": "NGINX"},
            {"name": "stable/nginx", "version": "1.2.3", "description": "NGINX old"},
        ]
    }

    try:
        r = client.get("/api/helm/search", params={"keyword": "nginx"})
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}"
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "bitnami/nginx"
    finally:
        helm_module._run_helm = original_run
        teardown()


def test_helm_releases_with_mock():
    """Test listing releases with mock data."""
    setup()

    original = helm_module._get_kubeconfig
    original_run = helm_module._run_helm

    helm_module._get_kubeconfig = lambda req: "/tmp/kubeconfig"
    helm_module._run_helm = lambda *a, **kw: {
        "data": [
            {
                "name": "nginx",
                "namespace": "default",
                "revision": "1",
                "updated": "2024-01-01",
                "status": "deployed",
                "chart": "nginx-15.0.0",
                "app_version": "1.25.0",
            },
            {
                "name": "prometheus",
                "namespace": "monitoring",
                "revision": "3",
                "updated": "2024-01-02",
                "status": "deployed",
                "chart": "prometheus-25.0.0",
                "app_version": "2.48.0",
            },
        ]
    }

    try:
        r = client.get("/api/helm/releases")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "nginx"
        assert data[0]["status"] == "deployed"
        assert data[1]["name"] == "prometheus"
    finally:
        helm_module._get_kubeconfig = original
        helm_module._run_helm = original_run
        teardown()


def test_helm_add_repo_validation():
    """Test that add repo validates required fields."""
    setup()
    r = client.post("/api/helm/repos", json={})
    assert r.status_code == 400, f"Expected 400 but got {r.status_code}"
    teardown()


def test_helm_repo_operations():
    """Test add and remove repo with mocked helm."""
    setup()

    original_run = helm_module._run_helm_raw
    helm_module._run_helm_raw = lambda *a, **kw: {
        "data": '"bitnami" has been added to your repositories'
    }

    try:
        r = client.post(
            "/api/helm/repos",
            json={"name": "bitnami", "url": "https://charts.bitnami.com/bitnami"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "added"
    finally:
        helm_module._run_helm_raw = original_run
        teardown()


if __name__ == "__main__":
    setup()
    tests = [
        ("helm_list_releases_endpoint", test_helm_list_releases_endpoint),
        ("helm_list_repos_endpoint", test_helm_list_repos_endpoint),
        ("helm_install_missing_fields", test_helm_install_missing_fields),
        ("helm_rollback_missing_revision", test_helm_rollback_missing_revision),
        ("helm_search_endpoint", test_helm_search_endpoint),
        ("helm_releases_with_mock", test_helm_releases_with_mock),
        ("helm_add_repo_validation", test_helm_add_repo_validation),
        ("helm_repo_operations", test_helm_repo_operations),
    ]
    for name, fn in tests:
        run_test(name, fn)
    teardown()
