"""
Test suite for Deployment Image Update API.

Tests the /api/resources/deployments/{name}/update-image endpoint
to verify that image updates are properly persisted.
"""

from fastapi.testclient import TestClient
from types import SimpleNamespace
import pytest
import json
from unittest.mock import MagicMock, patch

from app.main import app
import app.routes.deployments as deployments
from app.auth.session import get_current_user


class FakeDeployment:
    """Mock Deployment object with multiple containers"""

    def __init__(self, name, namespace="default", replicas=3):
        self.metadata = SimpleNamespace(
            name=name,
            namespace=namespace,
            uid="uid-" + name,
            creation_timestamp="2026-03-20T00:00:00Z",
            labels={"app": name},
            annotations={},
        )
        self.spec = SimpleNamespace(
            replicas=replicas,
            selector={"matchLabels": {"app": name}},
            template=SimpleNamespace(
                spec=SimpleNamespace(
                    containers=[
                        SimpleNamespace(name="nginx", image="nginx:1.19"),
                        SimpleNamespace(name="sidecar", image="sidecar:v1"),
                    ]
                )
            ),
        )
        self.status = SimpleNamespace(
            replicas=replicas,
            ready_replicas=replicas,
            updated_replicas=replicas,
            available_replicas=replicas,
            conditions=[],
        )


class FakeK8sClient:
    """Mock Kubernetes client for deployment tests"""

    def __init__(self):
        self.patch_calls = []
        self.deployment = FakeDeployment("test-deploy", "default")

    def AppsV1Api(self):
        class API:
            def __init__(self, outer):
                self._outer = outer

            def read_namespaced_deployment(self, name, namespace):
                return self._outer.deployment

            def patch_namespaced_deployment(
                self, name, namespace, patch, field_manager=None, _preload_content=True
            ):
                self._outer.patch_calls.append(
                    {
                        "name": name,
                        "namespace": namespace,
                        "patch": patch,
                        "field_manager": field_manager,
                    }
                )

                patch_dict = patch if isinstance(patch, dict) else json.loads(patch)

                if "spec" in patch_dict and "template" in patch_dict["spec"]:
                    template_spec = patch_dict["spec"]["template"].get("spec", {})
                    containers = template_spec.get("containers", [])

                    for i, container in enumerate(
                        self._outer.deployment.spec.template.spec.containers
                    ):
                        for patch_container in containers:
                            if patch_container.get("name") == container.name:
                                container.image = patch_container.get(
                                    "image", container.image
                                )

                return self._outer.deployment

        return API(self)


@pytest.fixture(autouse=True)
def setup_mocks(monkeypatch):
    """Setup auth bypass and mock database/k8s client for all tests"""
    app.dependency_overrides[get_current_user] = lambda: {
        "role": "admin",
        "email": "test@example.com",
    }

    fake_client = FakeK8sClient()

    mock_cluster = {"kubeconfig_path": "/fake/path"}

    with patch("app.routes.deployments.clusters") as mock_clusters:
        mock_clusters.find_one.return_value = mock_cluster

        with patch("app.routes.deployments.load_k8s_client", return_value=fake_client):
            yield fake_client

    app.dependency_overrides.clear()


client = TestClient(app)


class TestDeploymentImageUpdate:
    """Test deployment image update functionality"""

    def test_update_image_endpoint_exists(self, setup_mocks):
        """Test that the update-image endpoint exists"""
        response = client.patch(
            "/api/resources/deployments/test-deploy/update-image",
            json={"containerIndex": 0, "image": "nginx:1.21"},
            params={"cluster": "507f1f77bcf86cd799439011", "namespace": "default"},
        )

        assert response.status_code == 200, f"Endpoint failed: {response.text}"

    def test_update_image_includes_all_containers(self, setup_mocks):
        """Test that the patch includes ALL containers to prevent data loss"""
        fake_client = setup_mocks

        original_nginx_image = fake_client.deployment.spec.template.spec.containers[
            0
        ].image
        original_sidecar_image = fake_client.deployment.spec.template.spec.containers[
            1
        ].image

        response = client.patch(
            "/api/resources/deployments/test-deploy/update-image",
            json={"containerIndex": 0, "image": "nginx:1.21"},
            params={"cluster": "507f1f77bcf86cd799439011", "namespace": "default"},
        )

        assert response.status_code == 200

        assert len(fake_client.patch_calls) == 1
        patch_call = fake_client.patch_calls[0]

        patch = patch_call["patch"]

        assert "spec" in patch
        assert "template" in patch["spec"]
        assert "spec" in patch["spec"]["template"]
        assert "containers" in patch["spec"]["template"]["spec"]

        patched_containers = patch["spec"]["template"]["spec"]["containers"]

        container_names = [c["name"] for c in patched_containers]
        assert "nginx" in container_names, "nginx container must be in patch"
        assert "sidecar" in container_names, (
            "sidecar container must be in patch to prevent data loss"
        )

        nginx_container = next(c for c in patched_containers if c["name"] == "nginx")
        assert nginx_container["image"] == "nginx:1.21", "nginx image should be updated"

        sidecar_container = next(
            c for c in patched_containers if c["name"] == "sidecar"
        )
        assert sidecar_container["image"] == original_sidecar_image, (
            "sidecar image should remain unchanged"
        )

    def test_update_second_container_preserves_first(self, setup_mocks):
        """Test updating second container preserves first container's image"""
        fake_client = setup_mocks

        original_nginx_image = fake_client.deployment.spec.template.spec.containers[
            0
        ].image

        response = client.patch(
            "/api/resources/deployments/test-deploy/update-image",
            json={"containerIndex": 1, "image": "sidecar:v2"},
            params={"cluster": "507f1f77bcf86cd799439011", "namespace": "default"},
        )

        assert response.status_code == 200

        patch_call = fake_client.patch_calls[0]
        patched_containers = patch_call["patch"]["spec"]["template"]["spec"][
            "containers"
        ]

        nginx_container = next(c for c in patched_containers if c["name"] == "nginx")
        assert nginx_container["image"] == original_nginx_image, (
            "nginx image should be preserved"
        )

        sidecar_container = next(
            c for c in patched_containers if c["name"] == "sidecar"
        )
        assert sidecar_container["image"] == "sidecar:v2", (
            "sidecar image should be updated"
        )

    def test_update_image_returns_correct_container_name(self, setup_mocks):
        """Test that the API returns the correct container name in response"""
        response = client.patch(
            "/api/resources/deployments/test-deploy/update-image",
            json={"containerIndex": 0, "image": "nginx:1.21"},
            params={"cluster": "507f1f77bcf86cd799439011", "namespace": "default"},
        )

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "updated"
        assert "image" in data
        assert data["image"] == "nginx:1.21"
        assert data["container"] == "nginx"


class TestDeploymentYamlApply:
    """Test deployment YAML apply functionality

    Note: These tests verify the endpoint accepts the request and validates input.
    The actual server-side apply makes HTTP calls to the K8s API which cannot be mocked easily.
    """

    @pytest.mark.skip(reason="Requires actual Kubernetes API - tested manually")
    def test_yaml_apply_endpoint_exists(self, setup_mocks):
        """Test that the YAML apply endpoint exists"""
        pass

    @pytest.mark.skip(reason="Requires actual Kubernetes API - tested manually")
    def test_yaml_apply_uses_server_side_apply(self, setup_mocks):
        """Test that YAML apply uses server-side apply with force"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
