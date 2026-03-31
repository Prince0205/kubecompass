"""
Test Topology Graph Endpoints

Tests for the /api/topology/graph endpoint that builds Kubernetes
resource dependency graphs.
"""

from fastapi.testclient import TestClient
from types import SimpleNamespace
from app.main import app
from app.auth.session import get_current_user

client = TestClient(app)


class FakeItem:
    def __init__(
        self,
        name,
        namespace=None,
        uid=None,
        labels=None,
        owner_refs=None,
        replicas=None,
        ready_replicas=None,
        updated_replicas=None,
        unavailable_replicas=None,
        phase=None,
        node_name=None,
        container_statuses=None,
        containers=None,
        selector=None,
        service_type=None,
        cluster_ip=None,
        volume_name=None,
        schedule=None,
        active=None,
        desired_number_scheduled=None,
        number_ready=None,
        succeeded=None,
        failed=None,
        volume_name_pv=None,
        volumes=None,
        rules=None,
    ):
        self.metadata = SimpleNamespace(
            name=name,
            namespace=namespace,
            uid=uid or f"uid-{name}",
            labels=labels or {},
            owner_references=owner_refs or [],
            creation_timestamp=None,
        )
        self.spec = SimpleNamespace(
            replicas=replicas,
            selector=SimpleNamespace(match_labels=selector) if selector else None,
            node_name=node_name,
            containers=containers or [],
            type=service_type,
            cluster_ip=cluster_ip,
            volume_name=volume_name_pv,
            schedule=schedule,
            completions=1,
        )
        self.status = SimpleNamespace(
            phase=phase,
            ready_replicas=ready_replicas,
            updated_replicas=updated_replicas,
            unavailable_replicas=unavailable_replicas,
            pod_ip=None,
            host_ip=None,
            container_statuses=container_statuses or [],
            desired_number_scheduled=desired_number_scheduled,
            number_ready=number_ready,
            succeeded=succeeded,
            failed=failed,
            active=active or [],
        )


class FakeList:
    def __init__(self, items):
        self.items = items


def make_owner_ref(uid, kind):
    return SimpleNamespace(uid=uid, kind=kind)


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


def test_topology_endpoint_exists():
    """Test that the topology graph endpoint exists and returns 400 without session."""
    setup()
    r = client.get("/api/topology/graph")
    teardown()
    assert r.status_code in (400, 401, 403, 422), (
        f"Expected 400/401/403/422 but got {r.status_code}"
    )


def test_topology_returns_valid_structure():
    """Test that the topology endpoint returns the expected JSON structure
    when mocked with a fake k8s client."""
    setup()
    from app.routes import topology as topo_module

    original_get_context = topo_module.get_k8s_context

    def fake_get_context(request):
        fake_client = SimpleNamespace()

        # Fake CoreV1Api
        class FakeCoreV1:
            def list_pod_for_all_namespaces(self):
                return FakeList(
                    [
                        FakeItem(
                            "pod-1",
                            namespace="default",
                            uid="pod-uid-1",
                            phase="Running",
                            owner_refs=[make_owner_ref("rs-uid-1", "ReplicaSet")],
                        ),
                    ]
                )

            def list_namespaced_pod(self, ns):
                return FakeList(
                    [
                        FakeItem(
                            "pod-1",
                            namespace=ns,
                            uid="pod-uid-1",
                            phase="Running",
                            owner_refs=[make_owner_ref("rs-uid-1", "ReplicaSet")],
                        ),
                    ]
                )

            def list_service_for_all_namespaces(self):
                return FakeList(
                    [
                        FakeItem(
                            "svc-1",
                            namespace="default",
                            uid="svc-uid-1",
                            selector={"app": "test"},
                        ),
                    ]
                )

            def list_namespaced_service(self, ns):
                return FakeList(
                    [
                        FakeItem(
                            "svc-1",
                            namespace=ns,
                            uid="svc-uid-1",
                            selector={"app": "test"},
                        ),
                    ]
                )

            def list_config_map_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_config_map(self, ns):
                return FakeList([])

            def list_secret_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_secret(self, ns):
                return FakeList([])

            def list_persistent_volume_claim_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_persistent_volume_claim(self, ns):
                return FakeList([])

            def list_persistent_volume(self):
                return FakeList([])

        # Fake AppsV1Api
        class FakeAppsV1:
            def list_deployment_for_all_namespaces(self):
                return FakeList(
                    [
                        FakeItem(
                            "dep-1",
                            namespace="default",
                            uid="dep-uid-1",
                            replicas=3,
                            ready_replicas=3,
                            updated_replicas=3,
                            unavailable_replicas=0,
                        ),
                    ]
                )

            def list_namespaced_deployment(self, ns):
                return FakeList(
                    [
                        FakeItem(
                            "dep-1",
                            namespace=ns,
                            uid="dep-uid-1",
                            replicas=3,
                            ready_replicas=3,
                            updated_replicas=3,
                            unavailable_replicas=0,
                        ),
                    ]
                )

            def list_replica_set_for_all_namespaces(self):
                return FakeList(
                    [
                        FakeItem(
                            "rs-1",
                            namespace="default",
                            uid="rs-uid-1",
                            replicas=3,
                            ready_replicas=3,
                            owner_refs=[make_owner_ref("dep-uid-1", "Deployment")],
                        ),
                    ]
                )

            def list_namespaced_replica_set(self, ns):
                return FakeList(
                    [
                        FakeItem(
                            "rs-1",
                            namespace=ns,
                            uid="rs-uid-1",
                            replicas=3,
                            ready_replicas=3,
                            owner_refs=[make_owner_ref("dep-uid-1", "Deployment")],
                        ),
                    ]
                )

            def list_stateful_set_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_stateful_set(self, ns):
                return FakeList([])

            def list_daemon_set_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_daemon_set(self, ns):
                return FakeList([])

        # Fake BatchV1Api
        class FakeBatchV1:
            def list_job_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_job(self, ns):
                return FakeList([])

            def list_cron_job_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_cron_job(self, ns):
                return FakeList([])

        # Fake NetworkingV1Api
        class FakeNetworkingV1:
            def list_ingress_for_all_namespaces(self):
                return FakeList([])

            def list_namespaced_ingress(self, ns):
                return FakeList([])

        fake_client.CoreV1Api = FakeCoreV1
        fake_client.AppsV1Api = FakeAppsV1
        fake_client.BatchV1Api = FakeBatchV1
        fake_client.NetworkingV1Api = FakeNetworkingV1

        return fake_client, "default"

    topo_module.get_k8s_context = fake_get_context

    try:
        r = client.get("/api/topology/graph")
        assert r.status_code == 200, f"Expected 200 but got {r.status_code}: {r.text}"
        data = r.json()

        # Verify structure
        assert "nodes" in data, "Response missing 'nodes'"
        assert "edges" in data, "Response missing 'edges'"
        assert "total_nodes" in data, "Response missing 'total_nodes'"
        assert "total_edges" in data, "Response missing 'total_edges'"
        assert "namespace" in data, "Response missing 'namespace'"

        # Verify nodes
        assert len(data["nodes"]) >= 3, (
            f"Expected at least 3 nodes, got {len(data['nodes'])}"
        )

        # Verify node structure
        for node in data["nodes"]:
            assert "id" in node, "Node missing 'id'"
            assert "name" in node, "Node missing 'name'"
            assert "kind" in node, "Node missing 'kind'"
            assert "status" in node, "Node missing 'status'"
            assert "color" in node, "Node missing 'color'"

        # Verify edges
        for edge in data["edges"]:
            assert "source" in edge, "Edge missing 'source'"
            assert "target" in edge, "Edge missing 'target'"
            assert "label" in edge, "Edge missing 'label'"

        # Verify Deployment -> ReplicaSet -> Pod chain
        dep_node = next((n for n in data["nodes"] if n["kind"] == "Deployment"), None)
        rs_node = next((n for n in data["nodes"] if n["kind"] == "ReplicaSet"), None)
        pod_node = next((n for n in data["nodes"] if n["kind"] == "Pod"), None)

        assert dep_node is not None, "Deployment node not found"
        assert rs_node is not None, "ReplicaSet node not found"
        assert pod_node is not None, "Pod node not found"

        # Check ownership edges
        dep_to_rs = next(
            (
                e
                for e in data["edges"]
                if e["source"] == dep_node["id"]
                and e["target"] == rs_node["id"]
                and e["label"] == "owns"
            ),
            None,
        )
        assert dep_to_rs is not None, "Deployment -> ReplicaSet edge not found"

        rs_to_pod = next(
            (
                e
                for e in data["edges"]
                if e["source"] == rs_node["id"]
                and e["target"] == pod_node["id"]
                and e["label"] == "owns"
            ),
            None,
        )
        assert rs_to_pod is not None, "ReplicaSet -> Pod edge not found"

    finally:
        topo_module.get_k8s_context = original_get_context
        teardown()


def test_status_colors():
    """Test that status color mapping works correctly."""
    from app.routes.topology import _status_color

    assert _status_color("Running") == "green"
    assert _status_color("Active") == "green"
    assert _status_color("Healthy") == "green"
    assert _status_color("Bound") == "green"
    assert _status_color("Failed") == "red"
    assert _status_color("CrashLoopBackOff") == "red"
    assert _status_color("Pending") == "yellow"
    assert _status_color("Terminating") == "yellow"
    assert _status_color("Unknown") == "yellow"


if __name__ == "__main__":
    setup()
    tests = [
        ("topology_endpoint_exists", test_topology_endpoint_exists),
        ("topology_returns_valid_structure", test_topology_returns_valid_structure),
        ("status_colors", test_status_colors),
    ]
    for name, fn in tests:
        run_test(name, fn)
    teardown()
