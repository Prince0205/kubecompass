from fastapi.testclient import TestClient
from types import SimpleNamespace
import sys

from app.main import app
import app.routes.api_v1 as api_v1
from app.auth.session import get_current_user

client = TestClient(app)

class FakeItem:
    def __init__(self, name, group=None, versions=None, namespace=None, typ=None):
        self.metadata = SimpleNamespace(name=name, namespace=namespace)
        self.spec = SimpleNamespace(group=group, versions=[SimpleNamespace(name=v) for v in (versions or [])], type=typ)
        self.status = None

class FakeList:
    def __init__(self, items):
        self.items = items

class FakeKMod:
    def ApiextensionsV1Api(self):
        class API:
            def list_custom_resource_definition(self):
                return FakeList([FakeItem('crd.example.com', group='example.com', versions=['v1'])])
        return API()
    def CoreV1Api(self):
        class API:
            def list_persistent_volume(self):
                return FakeList([FakeItem('pv1')])
            def list_persistent_volume_claim_for_all_namespaces(self):
                return FakeList([FakeItem('pvc1', namespace='default')])
            def list_namespaced_persistent_volume_claim(self, namespace=None):
                return FakeList([FakeItem('pvc1', namespace=namespace)])
            def list_service_for_all_namespaces(self):
                return FakeList([FakeItem('svc1')])
            def list_namespaced_service(self, namespace=None):
                return FakeList([FakeItem('svc1')])
            def list_namespace(self):
                return FakeList([FakeItem('default')])
        return API()
    def StorageV1Api(self):
        class API:
            def list_storage_class(self):
                return FakeList([FakeItem('standard')])
        return API()
    def NetworkingV1Api(self):
        class API:
            def list_ingress_for_all_namespaces(self):
                return FakeList([FakeItem('ing1')])
            def list_namespaced_ingress(self, namespace=None):
                return FakeList([FakeItem('ing1')])
            def list_network_policy_for_all_namespaces(self):
                return FakeList([FakeItem('np1')])
            def list_namespaced_network_policy(self, namespace=None):
                return FakeList([FakeItem('np1')])
        return API()
    def RbacAuthorizationV1Api(self):
        class API:
            def list_role_for_all_namespaces(self):
                return FakeList([FakeItem('role1', namespace='default')])
            def list_cluster_role(self):
                return FakeList([FakeItem('clusterrole1')])
            def list_role_binding_for_all_namespaces(self):
                return FakeList([FakeItem('rb1', namespace='default')])
            def list_cluster_role_binding(self):
                return FakeList([FakeItem('crb1')])
            def list_namespaced_role(self, namespace=None):
                return FakeList([FakeItem('role1', namespace=namespace)])
            def list_namespaced_role_binding(self, namespace=None):
                return FakeList([FakeItem('rb1', namespace=namespace)])
        return API()


def setup():
    app.dependency_overrides[get_current_user] = lambda: {"role": "admin"}
    api_v1._get_api_client_for_request = lambda req: FakeKMod()


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


def test_crds():
    r = client.get('/v1/crds')
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert data[0]['name'] == 'crd.example.com'


def test_storage():
    r = client.get('/v1/storage')
    assert r.status_code == 200
    data = r.json()
    assert 'pv' in data and 'pvc' in data and 'sc' in data


def test_network():
    r = client.get('/v1/network')
    assert r.status_code == 200
    data = r.json()
    assert 'services' in data


def test_rbac():
    r = client.get('/v1/rbac')
    assert r.status_code == 200
    data = r.json()
    assert 'roles' in data and 'clusterroles' in data


def test_namespaces():
    r = client.get('/v1/namespaces')
    assert r.status_code == 200
    data = r.json()
    assert any(n['name']=='default' for n in data)


if __name__ == '__main__':
    setup()
    tests = [
        ('crds', test_crds),
        ('storage', test_storage),
        ('network', test_network),
        ('rbac', test_rbac),
        ('namespaces', test_namespaces),
    ]
    for name, fn in tests:
        run_test(name, fn)
    teardown()
