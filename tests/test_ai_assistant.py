"""
Test AI Assistant Endpoints

Tests for the /api/ai endpoints that provide natural language
Kubernetes operations.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.auth.session import get_current_user
from app.routes import ai_assistant as ai_module

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


def test_ai_status_endpoint():
    """Test that status endpoint returns configuration info."""
    setup()
    r = client.get("/api/ai/status")
    teardown()
    assert r.status_code == 200
    data = r.json()
    assert "llm_configured" in data
    assert "rule_based" in data
    assert "status" in data
    assert data["rule_based"] is True
    assert data["status"] == "ready"


def test_chat_empty_message():
    """Test that empty message returns 400."""
    setup()
    r = client.post("/api/ai/chat", json={"message": ""})
    teardown()
    assert r.status_code == 400


def test_chat_list_pods():
    """Test that 'list pods' returns correct command."""
    setup()

    original_ctx = ai_module._get_cluster_context
    ai_module._get_cluster_context = lambda req: {
        "namespace": "default",
        "context": "N/A",
    }

    try:
        r = client.post("/api/ai/chat", json={"message": "list pods"})
        assert r.status_code == 200
        data = r.json()
        assert data["command"] == "kubectl get pods -n default -o wide"
        assert data["source"] == "rule"
    finally:
        ai_module._get_cluster_context = original_ctx
        teardown()


def test_chat_list_deployments():
    """Test that 'list deployments' returns correct command."""
    setup()

    original_ctx = ai_module._get_cluster_context
    ai_module._get_cluster_context = lambda req: {
        "namespace": "default",
        "context": "N/A",
    }

    try:
        r = client.post("/api/ai/chat", json={"message": "show all deployments"})
        assert r.status_code == 200
        data = r.json()
        assert "get deployments" in data["command"]
        assert "default" in data["command"]
    finally:
        ai_module._get_cluster_context = original_ctx
        teardown()


def test_chat_scale_deployment():
    """Test that 'scale nginx to 5 replicas' returns correct command."""
    setup()

    original_ctx = ai_module._get_cluster_context
    ai_module._get_cluster_context = lambda req: {
        "namespace": "default",
        "context": "N/A",
    }

    try:
        r = client.post(
            "/api/ai/chat", json={"message": "scale deployment nginx to 5 replicas"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "scale" in data["command"]
        assert "nginx" in data["command"]
        assert "5" in data["command"]
        assert data["source"] == "rule"
        assert data["dry_run_command"] is not None
    finally:
        ai_module._get_cluster_context = original_ctx
        teardown()


def test_chat_restart_deployment():
    """Test that 'restart deployment' returns correct command."""
    setup()

    original_ctx = ai_module._get_cluster_context
    ai_module._get_cluster_context = lambda req: {
        "namespace": "default",
        "context": "N/A",
    }

    try:
        r = client.post("/api/ai/chat", json={"message": "restart deployment my-app"})
        assert r.status_code == 200
        data = r.json()
        assert "rollout restart" in data["command"]
        assert "my-app" in data["command"]
    finally:
        ai_module._get_cluster_context = original_ctx
        teardown()


def test_chat_show_logs():
    """Test that 'show logs' returns correct command."""
    setup()

    original_ctx = ai_module._get_cluster_context
    ai_module._get_cluster_context = lambda req: {
        "namespace": "default",
        "context": "N/A",
    }

    try:
        r = client.post("/api/ai/chat", json={"message": "show logs for my-pod"})
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data["command"]
        assert "my-pod" in data["command"]
    finally:
        ai_module._get_cluster_context = original_ctx
        teardown()


def test_chat_unrecognized():
    """Test that unrecognized input returns fallback."""
    setup()

    original_ctx = ai_module._get_cluster_context
    ai_module._get_cluster_context = lambda req: {
        "namespace": "default",
        "context": "N/A",
    }
    original_openai = ai_module._call_openai
    ai_module._call_openai = lambda msg, ctx: None

    try:
        r = client.post(
            "/api/ai/chat", json={"message": "do something completely random xyz123"}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "fallback"
        assert data["command"] is None
    finally:
        ai_module._get_cluster_context = original_ctx
        ai_module._call_openai = original_openai
        teardown()


def test_execute_empty_command():
    """Test that empty command returns 400."""
    setup()
    r = client.post("/api/ai/execute", json={"command": ""})
    teardown()
    assert r.status_code == 400


def test_execute_dangerous_command_blocked():
    """Test that dangerous commands are blocked."""
    setup()
    r = client.post(
        "/api/ai/execute", json={"command": "kubectl delete --force pod test"}
    )
    teardown()
    assert r.status_code == 400
    assert "dangerous" in r.json()["detail"].lower()


def test_execute_command():
    """Test executing a command with mock kubeconfig."""
    setup()

    original = ai_module._get_kubeconfig
    original_run = ai_module._run_command

    ai_module._get_kubeconfig = lambda req: "/tmp/kubeconfig"
    ai_module._run_command = lambda cmd, kc: {
        "exit_code": 0,
        "stdout": "NAME   READY   STATUS    RESTARTS   AGE\npod-1  1/1     Running   0          1d",
        "stderr": "",
        "success": True,
    }

    try:
        r = client.post("/api/ai/execute", json={"command": "kubectl get pods"})
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "pod-1" in data["stdout"]
    finally:
        ai_module._get_kubeconfig = original
        ai_module._run_command = original_run
        teardown()


def test_rule_based_patterns():
    """Test the rule-based pattern matching directly."""
    from app.routes.ai_assistant import _try_rule_based

    # Scale
    r = _try_rule_based("scale deployment nginx to 5 replicas", "default")
    assert r is not None
    assert "nginx" in r["command"]
    assert "5" in r["command"]

    # List pods
    r = _try_rule_based("list pods", "default")
    assert r is not None
    assert "get pods" in r["command"]

    # List services
    r = _try_rule_based("show all services", "default")
    assert r is not None
    assert "get services" in r["command"]

    # List nodes
    r = _try_rule_based("list nodes", "default")
    assert r is not None
    assert "get nodes" in r["command"]

    # Show events
    r = _try_rule_based("show events", "default")
    assert r is not None
    assert "get events" in r["command"]

    # Unrecognized
    r = _try_rule_based("asdfghjkl", "default")
    assert r is None


if __name__ == "__main__":
    setup()
    tests = [
        ("ai_status_endpoint", test_ai_status_endpoint),
        ("chat_empty_message", test_chat_empty_message),
        ("chat_list_pods", test_chat_list_pods),
        ("chat_list_deployments", test_chat_list_deployments),
        ("chat_scale_deployment", test_chat_scale_deployment),
        ("chat_restart_deployment", test_chat_restart_deployment),
        ("chat_show_logs", test_chat_show_logs),
        ("chat_unrecognized", test_chat_unrecognized),
        ("execute_empty_command", test_execute_empty_command),
        ("execute_dangerous_command_blocked", test_execute_dangerous_command_blocked),
        ("execute_command", test_execute_command),
        ("rule_based_patterns", test_rule_based_patterns),
    ]
    for name, fn in tests:
        run_test(name, fn)
    teardown()
