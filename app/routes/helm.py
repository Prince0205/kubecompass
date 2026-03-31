"""
Helm Manager Routes

Provides REST API endpoints for managing Helm releases:
- List installed releases with status, chart version, app version
- Search and browse Helm chart repositories
- Install, upgrade, and rollback releases
- View release history with diffs
- Add/remove Helm repositories
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.auth.session import get_current_user
from app.db import audit_logs
import subprocess
import json
import logging
import shlex

router = APIRouter(prefix="/api/helm")
logger = logging.getLogger(__name__)


def _run_helm(
    cmd_args: list, kubeconfig: str = None, namespace: str = None, timeout: int = 60
) -> dict:
    """Execute a helm CLI command and return parsed output."""
    args = ["helm"] + cmd_args + ["--output", "json"]
    if kubeconfig:
        args += ["--kubeconfig", kubeconfig]
    if namespace:
        args += ["--namespace", namespace]

    logger.info(f"Running: {' '.join(args)}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error(f"Helm command failed (rc={result.returncode}): {stderr}")
            return {"error": stderr, "returncode": result.returncode}

        stdout = result.stdout.strip()
        if not stdout:
            return {"data": []}
        try:
            return {"data": json.loads(stdout)}
        except json.JSONDecodeError:
            return {"data": stdout}
    except subprocess.TimeoutExpired:
        return {"error": f"Helm command timed out after {timeout}s"}
    except FileNotFoundError:
        return {"error": "Helm CLI not found. Please install Helm on the server."}
    except Exception as e:
        return {"error": str(e)}


def _run_helm_raw(
    cmd_args: list, kubeconfig: str = None, namespace: str = None, timeout: int = 60
) -> dict:
    """Execute a helm CLI command and return raw text output."""
    args = ["helm"] + cmd_args
    if kubeconfig:
        args += ["--kubeconfig", kubeconfig]
    if namespace:
        args += ["--namespace", namespace]

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "returncode": result.returncode}
        return {"data": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"error": f"Helm command timed out after {timeout}s"}
    except FileNotFoundError:
        return {"error": "Helm CLI not found. Please install Helm on the server."}
    except Exception as e:
        return {"error": str(e)}


def _get_kubeconfig(request: Request):
    """Get the kubeconfig path for the active cluster."""
    from app.db import clusters
    from bson import ObjectId

    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(404, "Cluster not found")

    return cluster.get("kubeconfig_path")


@router.get("/releases")
def list_releases(
    request: Request,
    namespace: str = Query(None),
    all_namespaces: bool = Query(False),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """List all installed Helm releases."""
    kubeconfig = _get_kubeconfig(request)
    ns = namespace or request.session.get("active_namespace", "default")

    cmd = ["list"]
    if all_namespaces:
        cmd += ["-A"]

    result = _run_helm(
        cmd, kubeconfig=kubeconfig, namespace=None if all_namespaces else ns
    )
    if "error" in result:
        if "not found" in result.get("error", "").lower():
            return []
        raise HTTPException(500, f"Failed to list releases: {result['error']}")

    data = result.get("data", [])
    # Normalize field names (helm versions differ: Name vs name, etc.)
    if isinstance(data, list):
        normalized = []
        for item in data:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "name": item.get("name") or item.get("Name", ""),
                        "namespace": item.get("namespace") or item.get("Namespace", ""),
                        "revision": item.get("revision") or item.get("Revision", ""),
                        "updated": item.get("updated") or item.get("Updated", ""),
                        "status": item.get("status") or item.get("Status", ""),
                        "chart": item.get("chart") or item.get("Chart", ""),
                        "app_version": item.get("app_version")
                        or item.get("AppVersion", ""),
                    }
                )
        return normalized
    return []


@router.get("/releases/{release_name}/history")
def release_history(
    release_name: str,
    request: Request,
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get the revision history of a Helm release."""
    kubeconfig = _get_kubeconfig(request)
    ns = namespace or request.session.get("active_namespace", "default")

    cmd = ["history", release_name, "--max", "20"]
    result = _run_helm(cmd, kubeconfig=kubeconfig, namespace=ns)
    if "error" in result:
        raise HTTPException(500, f"Failed to get history: {result['error']}")
    return result.get("data", [])


@router.get("/releases/{release_name}/values")
def release_values(
    release_name: str,
    request: Request,
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get the user-supplied values of a Helm release."""
    kubeconfig = _get_kubeconfig(request)
    ns = namespace or request.session.get("active_namespace", "default")

    cmd = ["get", "values", release_name]
    result = _run_helm_raw(cmd, kubeconfig=kubeconfig, namespace=ns)
    if "error" in result:
        raise HTTPException(500, f"Failed to get values: {result['error']}")
    return {"values": result.get("data", "")}


@router.get("/releases/{release_name}/manifest")
def release_manifest(
    release_name: str,
    request: Request,
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get the rendered manifest of a Helm release."""
    kubeconfig = _get_kubeconfig(request)
    ns = namespace or request.session.get("active_namespace", "default")

    cmd = ["get", "manifest", release_name]
    result = _run_helm_raw(cmd, kubeconfig=kubeconfig, namespace=ns)
    if "error" in result:
        raise HTTPException(500, f"Failed to get manifest: {result['error']}")
    return {"manifest": result.get("data", "")}


@router.get("/releases/{release_name}/notes")
def release_notes(
    release_name: str,
    request: Request,
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get the notes of a Helm release."""
    kubeconfig = _get_kubeconfig(request)
    ns = namespace or request.session.get("active_namespace", "default")

    cmd = ["get", "notes", release_name]
    result = _run_helm_raw(cmd, kubeconfig=kubeconfig, namespace=ns)
    if "error" in result:
        raise HTTPException(500, f"Failed to get notes: {result['error']}")
    return {"notes": result.get("data", "")}


@router.get("/chart-values")
def chart_default_values(
    chart: str = Query(...),
    version: str = Query(None),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Get the default values.yaml for a chart before installing."""
    cmd = ["show", "values", chart]
    if version:
        cmd += ["--version", version]

    result = _run_helm_raw(cmd, timeout=60)
    if "error" in result:
        raise HTTPException(500, f"Failed to get chart values: {result['error']}")
    return {"values": result.get("data", "")}


@router.post("/releases")
def install_release(
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Install a new Helm release with optional custom values."""
    kubeconfig = _get_kubeconfig(request)
    chart = body.get("chart")
    release_name = body.get("name")
    namespace = body.get(
        "namespace", request.session.get("active_namespace", "default")
    )
    values = body.get("values", "")
    version = body.get("version", "")

    if not chart or not release_name:
        raise HTTPException(400, "chart and name are required")

    cmd = [
        "install",
        release_name,
        chart,
        "--namespace",
        namespace,
        "--create-namespace",
    ]
    if version:
        cmd += ["--version", version]

    # Write values to a temp file if provided
    import tempfile

    values_file = None
    if values and values.strip():
        try:
            values_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            )
            values_file.write(values)
            values_file.close()
            cmd += ["--values", values_file.name]
        except Exception as e:
            logger.error(f"Failed to write values file: {e}")
            raise HTTPException(500, f"Failed to process values: {str(e)}")

    try:
        result = _run_helm_raw(cmd, kubeconfig=kubeconfig, timeout=120)
    finally:
        # Clean up temp file
        if values_file:
            import os

            try:
                os.unlink(values_file.name)
            except Exception:
                pass

    if "error" in result:
        raise HTTPException(500, f"Failed to install: {result['error']}")

    user_email = user.get("email", "unknown") if isinstance(user, dict) else str(user)
    try:
        audit_logs.insert_one(
            {
                "action": "helm_install",
                "user": user_email,
                "release": release_name,
                "chart": chart,
                "namespace": namespace,
                "version": version,
            }
        )
    except Exception:
        pass

    return {"status": "installed", "output": result.get("data", "")}


@router.put("/releases/{release_name}")
def upgrade_release(
    release_name: str,
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Upgrade an existing Helm release."""
    kubeconfig = _get_kubeconfig(request)
    chart = body.get("chart")
    namespace = body.get(
        "namespace", request.session.get("active_namespace", "default")
    )
    version = body.get("version", "")

    if not chart:
        raise HTTPException(400, "chart is required")

    cmd = ["upgrade", release_name, chart, "--namespace", namespace]
    if version:
        cmd += ["--version", version]

    result = _run_helm_raw(cmd, kubeconfig=kubeconfig, timeout=120)
    if "error" in result:
        raise HTTPException(500, f"Failed to upgrade: {result['error']}")

    user_email = user.get("email", "unknown") if isinstance(user, dict) else str(user)
    try:
        audit_logs.insert_one(
            {
                "action": "helm_upgrade",
                "user": user_email,
                "release": release_name,
                "chart": chart,
                "namespace": namespace,
                "version": version,
            }
        )
    except Exception:
        pass

    return {"status": "upgraded", "output": result.get("data", "")}


@router.post("/releases/{release_name}/rollback")
def rollback_release(
    release_name: str,
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Rollback a Helm release to a previous revision."""
    kubeconfig = _get_kubeconfig(request)
    revision = body.get("revision")
    namespace = body.get(
        "namespace", request.session.get("active_namespace", "default")
    )

    if revision is None:
        raise HTTPException(400, "revision is required")

    cmd = ["rollback", release_name, str(revision), "--namespace", namespace]
    result = _run_helm_raw(cmd, kubeconfig=kubeconfig, timeout=120)
    if "error" in result:
        raise HTTPException(500, f"Failed to rollback: {result['error']}")

    user_email = user.get("email", "unknown") if isinstance(user, dict) else str(user)
    try:
        audit_logs.insert_one(
            {
                "action": "helm_rollback",
                "user": user_email,
                "release": release_name,
                "revision": revision,
                "namespace": namespace,
            }
        )
    except Exception:
        pass

    return {"status": "rolled back", "output": result.get("data", "")}


@router.delete("/releases/{release_name}")
def uninstall_release(
    release_name: str,
    request: Request,
    namespace: str = Query(None),
    user=Depends(require_role(["admin", "edit"])),
):
    """Uninstall a Helm release."""
    kubeconfig = _get_kubeconfig(request)
    ns = namespace or request.session.get("active_namespace", "default")

    cmd = ["uninstall", release_name, "--namespace", ns]
    result = _run_helm_raw(cmd, kubeconfig=kubeconfig)
    if "error" in result:
        raise HTTPException(500, f"Failed to uninstall: {result['error']}")

    user_email = user.get("email", "unknown") if isinstance(user, dict) else str(user)
    try:
        audit_logs.insert_one(
            {
                "action": "helm_uninstall",
                "user": user_email,
                "release": release_name,
                "namespace": ns,
            }
        )
    except Exception:
        pass

    return {"status": "uninstalled", "output": result.get("data", "")}


@router.get("/repos")
def list_repos(
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """List configured Helm repositories."""
    cmd = ["repo", "list"]
    result = _run_helm(cmd)
    if "error" in result:
        err = result["error"]
        # "no repositories" is a normal state, not an error
        if "no repositories" in err.lower():
            return []
        # Log real errors but still return empty to avoid breaking the UI
        logger.warning(f"helm repo list failed: {err}")
        return []
    data = result.get("data", [])
    if isinstance(data, list):
        # Normalize field names (helm versions differ)
        normalized = []
        for item in data:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "name": item.get("name") or item.get("Name", ""),
                        "url": item.get("url") or item.get("URL", ""),
                    }
                )
        return normalized
    return []


@router.post("/repos")
def add_repo(
    body: dict,
    user=Depends(require_role(["admin"])),
):
    """Add a Helm repository."""
    name = body.get("name")
    url = body.get("url")
    if not name or not url:
        raise HTTPException(400, "name and url are required")

    cmd = ["repo", "add", name, url]
    result = _run_helm_raw(cmd, timeout=30)
    if "error" in result:
        raise HTTPException(500, f"Failed to add repo: {result['error']}")

    return {"status": "added", "output": result.get("data", "")}


@router.delete("/repos/{repo_name}")
def remove_repo(
    repo_name: str,
    user=Depends(require_role(["admin"])),
):
    """Remove a Helm repository."""
    cmd = ["repo", "remove", repo_name]
    result = _run_helm_raw(cmd)
    if "error" in result:
        raise HTTPException(500, f"Failed to remove repo: {result['error']}")
    return {"status": "removed"}


@router.post("/repos/update")
def update_repos(
    user=Depends(require_role(["admin", "edit"])),
):
    """Update all Helm repositories."""
    cmd = ["repo", "update"]
    result = _run_helm_raw(cmd, timeout=120)
    if "error" in result:
        raise HTTPException(500, f"Failed to update repos: {result['error']}")
    return {"status": "updated", "output": result.get("data", "")}


@router.get("/search")
def search_charts(
    keyword: str = Query(...),
    repo: str = Query(None),
    max_results: int = Query(20),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Search for charts in configured repositories."""
    cmd = ["search", "repo", keyword, "--max-col-width", "80"]
    if repo:
        cmd = ["search", "repo", f"{repo}/{keyword}", "--max-col-width", "80"]

    result = _run_helm(cmd + ["--output", "json"], timeout=30)
    if "error" in result:
        return []
    data = result.get("data", [])
    if isinstance(data, list):
        return data[:max_results]
    return []


@router.get("/search/hub")
def search_hub(
    keyword: str = Query(...),
    max_results: int = Query(20),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Search the Helm Hub for charts."""
    cmd = ["search", "hub", keyword, "--max-col-width", "80", "--output", "json"]
    result = _run_helm(cmd, timeout=30)
    if "error" in result:
        return []
    data = result.get("data", [])
    if isinstance(data, list):
        return data[:max_results]
    return []
