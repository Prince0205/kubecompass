import asyncio
import threading
import logging

from fastapi import (
    APIRouter,
    Request,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth.rbac import require_role
from app.db import clusters
from bson import ObjectId
from app.k8s.loader import load_k8s_client
import yaml

logger = logging.getLogger(__name__)

ui_router = APIRouter()
api_router = APIRouter(prefix="/api/resources/pods")
templates = Jinja2Templates(directory="app/templates")


def get_context(request):
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace")

    if not cluster_id or not namespace:
        raise HTTPException(400, "Cluster or namespace not selected")

    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    k8s = load_k8s_client(cluster["kubeconfig_path"])

    return k8s, namespace


@ui_router.get("/pods", response_class=HTMLResponse)
def pods_page(request: Request, user=Depends(require_role(["admin", "edit", "view"]))):
    return templates.TemplateResponse("pods.html", {"request": request, "user": user})


@api_router.get("/{pod_name}")
def pod_details(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    pod = v1.read_namespaced_pod(pod_name, namespace)

    # Determine effective status from container states
    effective_status = pod.status.phase
    for cs in pod.status.container_statuses or []:
        if cs.state and cs.state.waiting:
            reason = cs.state.waiting.reason or ""
            if reason in (
                "CrashLoopBackOff",
                "ImagePullBackOff",
                "ErrImagePull",
                "CreateContainerConfigError",
                "CreateContainerError",
                "RunContainerError",
                "InvalidImageName",
            ):
                effective_status = reason
                break
        elif cs.state and cs.state.terminated:
            reason = cs.state.terminated.reason or ""
            if reason in ("Error", "OOMKilled", "ContainerCannotRun"):
                effective_status = reason
                break

    return {
        "name": pod.metadata.name,
        "namespace": namespace,
        "node": pod.spec.node_name,
        "status": effective_status,
        "containers": [c.name for c in pod.spec.containers],
        "images": [c.image for c in pod.spec.containers],
        "restarts": sum(
            cs.restart_count for cs in (pod.status.container_statuses or [])
        ),
    }


@api_router.get("/{pod_name}/events")
def pod_events(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    events = v1.list_namespaced_event(namespace).items

    return [
        {
            "type": e.type,
            "reason": e.reason,
            "message": e.message,
            "time": e.last_timestamp or e.event_time,
        }
        for e in events
        if e.involved_object
        and e.involved_object.kind == "Pod"
        and e.involved_object.name == pod_name
    ]


@api_router.get("/{pod_name}/logs")
def pod_logs(
    pod_name: str,
    request: Request,
    container: str = Query(None),
    tail: int = Query(200),
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    logs = v1.read_namespaced_pod_log(
        name=pod_name, namespace=namespace, container=container, tail_lines=tail
    )

    return {"logs": logs}


@api_router.delete("/{pod_name}")
def delete_pod(
    pod_name: str, request: Request, user=Depends(require_role(["admin", "edit"]))
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    v1.delete_namespaced_pod(name=pod_name, namespace=namespace)

    return {"status": "deleted"}


@api_router.get("/{pod_name}/yaml")
def pod_yaml(
    pod_name: str,
    request: Request,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    k8s, namespace = get_context(request)
    v1 = k8s.CoreV1Api()

    pod = v1.read_namespaced_pod(pod_name, namespace)

    # Remove runtime-only fields
    pod.metadata.managed_fields = None
    pod.metadata.resource_version = None
    pod.metadata.uid = None
    pod.metadata.creation_timestamp = None
    pod.status = None

    return {"yaml": yaml.safe_dump(pod.to_dict(), sort_keys=False), "editable": False}


@api_router.websocket("/{pod_name}/exec")
async def pod_exec_ws(
    websocket: WebSocket,
    pod_name: str,
):
    """WebSocket endpoint for exec into a pod (like kubectl exec -it).

    Query params:
        container: container name to exec into
        shell: shell to use (default: /bin/sh)
    """
    from kubernetes.stream import stream as k8s_stream
    from kubernetes.client import Configuration
    import ssl

    await websocket.accept()

    try:
        # Get session data from cookies
        session_data = websocket.scope.get("session", {})
        cluster_id = session_data.get("active_cluster")
        namespace = session_data.get("active_namespace", "default")

        if not cluster_id:
            await websocket.send_text("\r\nError: No active cluster selected\r\n")
            await websocket.close()
            return

        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            await websocket.send_text("\r\nError: Cluster not found\r\n")
            await websocket.close()
            return

        # Get query params
        container = websocket.query_params.get("container", "")
        shell = websocket.query_params.get("shell", "/bin/sh")

        # Load k8s client
        k8s = load_k8s_client(cluster["kubeconfig_path"])
        v1 = k8s.CoreV1Api()

        # If no container specified, get the first one
        if not container:
            pod = v1.read_namespaced_pod(pod_name, namespace)
            if pod.spec.containers:
                container = pod.spec.containers[0].name

        # Create exec connection using kubernetes stream
        k8s_ws = k8s_stream(
            v1.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            container=container,
            command=[shell],
            stderr=True,
            stdin=True,
            stdout=True,
            tty=True,
            _preload_content=False,
        )

        await websocket.send_text(
            f"\r\nConnected to {container} in {pod_name} ({namespace})\r\n"
        )

        loop = asyncio.get_event_loop()
        output_event = threading.Event()
        should_stop = threading.Event()

        def read_k8s_output():
            """Thread: read from K8s exec and forward to browser WebSocket."""
            try:
                while not should_stop.is_set():
                    try:
                        data = k8s_ws.read_stdout(timeout=0.5)
                        if data:
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_bytes(data), loop
                            )
                    except Exception:
                        pass

                    try:
                        data = k8s_ws.read_stderr(timeout=0.1)
                        if data:
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_bytes(data), loop
                            )
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"K8s read thread ended: {e}")
            finally:
                output_event.set()

        # Start background thread for reading K8s output
        reader_thread = threading.Thread(target=read_k8s_output, daemon=True)
        reader_thread.start()

        try:
            # Main loop: read from browser WebSocket, write to K8s exec
            while True:
                try:
                    data = await websocket.receive()
                except WebSocketDisconnect:
                    break

                if "bytes" in data:
                    await loop.run_in_executor(None, k8s_ws.write_stdin, data["bytes"])
                elif "text" in data:
                    await loop.run_in_executor(
                        None, k8s_ws.write_stdin, data["text"].encode("utf-8")
                    )

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            should_stop.set()
            try:
                k8s_ws.close()
            except Exception:
                pass
            output_event.wait(timeout=2)

    except Exception as e:
        logger.error(f"Pod exec error: {e}")
        try:
            await websocket.send_text(f"\r\nError: {str(e)}\r\n")
        except Exception:
            pass
        await websocket.close()
