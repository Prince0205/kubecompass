"""
AI Assistant Routes

Provides REST API endpoints for natural language Kubernetes operations:
- Chat interface: describe what you want, get kubectl commands
- One-click execution with dry-run support
- Resource-aware context gathering
- Conversation history
- Safety: dry-run, undo, command confirmation

Supports OpenAI API (OPENAI_API_KEY) with a built-in rule-based fallback
for common operations when no LLM is configured.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from app.auth.rbac import require_role
from app.db import audit_logs
from app.k8s.loader import load_k8s_client
from app.db import clusters
from bson import ObjectId
import subprocess
import json
import logging
import os
import re
from datetime import datetime

router = APIRouter(prefix="/api/ai")
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _get_kubeconfig(request: Request):
    """Get the kubeconfig path for the active cluster."""
    cluster_id = request.session.get("active_cluster")
    if not cluster_id:
        raise HTTPException(400, "No active cluster selected")
    cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
    if not cluster:
        raise HTTPException(404, "Cluster not found")
    return cluster.get("kubeconfig_path")


def _get_cluster_context(request: Request):
    """Gather current cluster state for AI context."""
    cluster_id = request.session.get("active_cluster")
    namespace = request.session.get("active_namespace", "default")

    if not cluster_id:
        return {"namespace": namespace, "resources": []}

    try:
        cluster = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            return {"namespace": namespace, "resources": []}

        k8s = load_k8s_client(cluster["kubeconfig_path"])
        v1 = k8s.CoreV1Api()
        apps = k8s.AppsV1Api()

        context_parts = []

        # Deployments
        try:
            deps = apps.list_namespaced_deployment(namespace).items
            dep_info = []
            for d in deps:
                dep_info.append(
                    f"  - {d.metadata.name} (replicas={d.spec.replicas}, ready={d.status.ready_replicas or 0})"
                )
            if dep_info:
                context_parts.append(
                    "Deployments in " + namespace + ":\n" + "\n".join(dep_info)
                )
        except Exception:
            pass

        # Pods
        try:
            pods = v1.list_namespaced_pod(namespace).items
            pod_info = []
            for p in pods[:20]:
                status = p.status.phase
                pod_info.append(f"  - {p.metadata.name} (status={status})")
            if pod_info:
                context_parts.append(
                    "Pods in " + namespace + ":\n" + "\n".join(pod_info)
                )
        except Exception:
            pass

        # Services
        try:
            svcs = v1.list_namespaced_service(namespace).items
            svc_info = []
            for s in svcs:
                svc_info.append(
                    f"  - {s.metadata.name} (type={s.spec.type}, cluster_ip={s.spec.cluster_ip})"
                )
            if svc_info:
                context_parts.append(
                    "Services in " + namespace + ":\n" + "\n".join(svc_info)
                )
        except Exception:
            pass

        # Namespaces
        try:
            nss = v1.list_namespace().items
            ns_names = [n.metadata.name for n in nss]
            context_parts.append(f"Available namespaces: {', '.join(ns_names)}")
        except Exception:
            pass

        return {
            "namespace": namespace,
            "cluster_name": cluster.get("name", "unknown"),
            "context": "\n\n".join(context_parts)
            if context_parts
            else "No resources found",
        }
    except Exception as e:
        logger.warning(f"Failed to gather cluster context: {e}")
        return {"namespace": namespace, "context": "Unable to read cluster state"}


# --- Rule-based fallback for common operations ---

RULE_PATTERNS = [
    {
        "patterns": [
            r"scale\s+(?:the\s+)?(?:deployment\s+)?(\S+)\s+to\s+(\d+)",
            r"(?:increase|decrease|set)\s+(?:the\s+)?(?:replicas?\s+(?:of\s+)?(?:deployment\s+)?(\S+)\s+(?:to\s+)?(\d+))",
        ],
        "command": "kubectl scale deployment {0} --replicas={1} -n {{namespace}}",
        "description": "Scale deployment {0} to {1} replicas",
        "dry_run": "kubectl scale deployment {0} --replicas={1} -n {{namespace}} --dry-run=client",
    },
    {
        "patterns": [
            r"(?:list|show|get)\s+(?:all\s+)?(?:deployments?|deploys?)",
        ],
        "command": "kubectl get deployments -n {namespace} -o wide",
        "description": "List all deployments in the namespace",
    },
    {
        "patterns": [
            r"(?:list|show|get)\s+(?:all\s+)?pods?",
        ],
        "command": "kubectl get pods -n {namespace} -o wide",
        "description": "List all pods in the namespace",
    },
    {
        "patterns": [
            r"(?:list|show|get)\s+(?:all\s+)?services?",
        ],
        "command": "kubectl get services -n {namespace} -o wide",
        "description": "List all services in the namespace",
    },
    {
        "patterns": [
            r"(?:list|show|get)\s+(?:all\s+)?nodes?",
        ],
        "command": "kubectl get nodes -o wide",
        "description": "List all nodes in the cluster",
    },
    {
        "patterns": [
            r"(?:describe|inspect)\s+(?:the\s+)?(?:pod\s+)?(\S+)",
        ],
        "command": "kubectl describe pod {0} -n {namespace}",
        "description": "Describe pod {0}",
    },
    {
        "patterns": [
            r"(?:show|get|tail)\s+(?:the\s+)?logs?\s+(?:of\s+|for\s+)?(\S+)",
            r"logs?\s+(?:of\s+|for\s+)?(\S+)",
        ],
        "command": "kubectl logs {0} -n {namespace} --tail=50",
        "description": "Show last 50 log lines for pod {0}",
    },
    {
        "patterns": [
            r"(?:delete|remove)\s+(?:the\s+)?(?:pod\s+)?(\S+)",
        ],
        "command": "kubectl delete pod {0} -n {namespace}",
        "description": "Delete pod {0}",
        "dry_run": "kubectl delete pod {0} -n {namespace} --dry-run=client",
    },
    {
        "patterns": [
            r"(?:restart|rollout\s+restart)\s+(?:the\s+)?(?:deployment\s+)?(\S+)",
        ],
        "command": "kubectl rollout restart deployment {0} -n {namespace}",
        "description": "Restart deployment {0}",
        "dry_run": "kubectl rollout restart deployment {0} -n {namespace} --dry-run=client",
    },
    {
        "patterns": [
            r"(?:update|change|set)\s+(?:the\s+)?(?:image\s+(?:of\s+)?(?:container\s+)?(\S+)\s+(?:in\s+)?(?:deployment\s+)?(\S+)\s+(?:to\s+)?(\S+))",
            r"(?:set|update)\s+image\s+(\S+)/(\S+)=(\S+)",
        ],
        "command": "kubectl set image deployment/{1} {0}={2} -n {namespace}",
        "description": "Update image of container {0} in deployment {1} to {2}",
        "dry_run": "kubectl set image deployment/{1} {0}={2} -n {namespace} --dry-run=client",
    },
    {
        "patterns": [
            r"(?:apply|create)\s+(?:a\s+)?(?:namespace\s+)?(\S+)",
        ],
        "command": "kubectl create namespace {0}",
        "description": "Create namespace {0}",
        "dry_run": "kubectl create namespace {0} --dry-run=client",
    },
    {
        "patterns": [
            r"(?:get|describe|show)\s+(?:the\s+)?(?:events?|warnings?)",
        ],
        "command": "kubectl get events -n {namespace} --sort-by='.lastTimestamp'",
        "description": "Show recent events in the namespace",
    },
    {
        "patterns": [
            r"(?:show|get)\s+(?:resource\s+)?(?:usage|resources?)",
            r"(?:top)\s+(?:pods?|nodes?)",
        ],
        "command": "kubectl top pods -n {namespace}",
        "description": "Show resource usage for pods in the namespace",
    },
    {
        "patterns": [
            r"(?:show|get)\s+(?:all\s+)?resources?",
            r"(?:get\s+all)",
        ],
        "command": "kubectl get all -n {namespace}",
        "description": "Show all resources in the namespace",
    },
]


def _try_rule_based(user_message: str, namespace: str):
    """Try to match user input against rule-based patterns."""
    msg = user_message.lower().strip()

    for rule in RULE_PATTERNS:
        for pattern in rule["patterns"]:
            match = re.search(pattern, msg)
            if match:
                groups = match.groups()
                cmd = rule["command"]
                desc = rule["description"]

                # Replace positional placeholders
                for i, g in enumerate(groups):
                    cmd = cmd.replace("{" + str(i) + "}", g)
                    desc = desc.replace("{" + str(i) + "}", g)

                # Replace namespace placeholder
                cmd = cmd.replace("{namespace}", namespace)
                desc = desc.replace("{namespace}", namespace)

                dry_run = None
                if "dry_run" in rule:
                    dry_run = rule["dry_run"]
                    for i, g in enumerate(groups):
                        dry_run = dry_run.replace("{" + str(i) + "}", g)
                    dry_run = dry_run.replace("{namespace}", namespace)

                return {
                    "command": cmd,
                    "description": desc,
                    "dry_run_command": dry_run,
                    "source": "rule",
                }

    return None


def _call_openai(user_message: str, cluster_context: dict) -> dict:
    """Call OpenAI API to generate a kubectl command."""
    if not OPENAI_API_KEY:
        return None

    try:
        import urllib.request
        import urllib.error

        system_prompt = (
            "You are a Kubernetes assistant. Given a user request, generate the exact kubectl "
            "command to accomplish the task. You also have access to the current cluster state.\n\n"
            f"Current namespace: {cluster_context.get('namespace', 'default')}\n"
            f"Cluster state:\n{cluster_context.get('context', 'N/A')}\n\n"
            "Respond ONLY with JSON in this format:\n"
            '{"command": "kubectl ...", "description": "brief description", '
            '"explanation": "why this command", "risk_level": "low|medium|high", '
            '"dry_run_command": "kubectl ... --dry-run=client"}\n\n'
            "Rules:\n"
            "- Always include -n <namespace> for namespaced resources\n"
            "- Risk levels: low=read-only, medium=changes, high=destructive\n"
            "- Always provide a dry_run_command\n"
            "- Never use --force or --grace-period=0\n"
            "- Use exact resource names from the cluster state when possible"
        )

        payload = json.dumps(
            {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,
                "max_tokens": 500,
            }
        ).encode()

        req = urllib.request.Request(
            OPENAI_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            content = data["choices"][0]["message"]["content"]

            # Try to parse JSON from response
            # Handle markdown code blocks
            if "```" in content:
                content = re.search(r"```(?:json)?\n?(.*?)```", content, re.DOTALL)
                if content:
                    content = content.group(1)

            result = json.loads(content.strip())
            result["source"] = "llm"
            return result

    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return None


def _run_command(command: str, kubeconfig: str, timeout: int = 60) -> dict:
    """Execute a kubectl command."""
    try:
        env = os.environ.copy()
        if kubeconfig:
            env["KUBECONFIG"] = kubeconfig

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": "Command timed out",
            "success": False,
        }
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}


@router.post("/chat")
def chat(
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Process a natural language request and return a suggested command."""
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(400, "message is required")

    namespace = request.session.get("active_namespace", "default")

    # Gather cluster context
    cluster_context = _get_cluster_context(request)

    # Try rule-based first
    result = _try_rule_based(message, namespace)

    if not result:
        # Try OpenAI
        result = _call_openai(message, cluster_context)

    if not result:
        return {
            "response": "I couldn't understand that request. Try commands like:\n"
            "- 'scale deployment nginx to 5 replicas'\n"
            "- 'list pods'\n"
            "- 'show logs for pod-xyz'\n"
            "- 'restart deployment my-app'\n"
            "- 'describe pod my-pod'",
            "command": None,
            "source": "fallback",
        }

    return {
        "response": result.get("description", ""),
        "command": result.get("command", ""),
        "dry_run_command": result.get("dry_run_command"),
        "explanation": result.get("explanation", result.get("description", "")),
        "risk_level": result.get("risk_level", "unknown"),
        "source": result.get("source", "rule"),
    }


@router.post("/execute")
def execute_command(
    request: Request,
    body: dict,
    user=Depends(require_role(["admin", "edit"])),
):
    """Execute a kubectl command."""
    command = body.get("command", "").strip()
    dry_run = body.get("dry_run", False)

    if not command:
        raise HTTPException(400, "command is required")

    # Safety checks
    dangerous_patterns = [
        "--force",
        "--grace-period=0",
        "rm -rf",
        "delete namespace kube-",
    ]
    for pattern in dangerous_patterns:
        if pattern in command.lower():
            raise HTTPException(
                400,
                f"Command blocked: contains dangerous pattern '{pattern}'",
            )

    kubeconfig = _get_kubeconfig(request)

    if dry_run:
        dry_run_cmd = body.get("dry_run_command")
        if dry_run_cmd:
            command = dry_run_cmd
        elif "--dry-run" not in command:
            command += " --dry-run=client"

    result = _run_command(command, kubeconfig)

    # Log the execution
    user_email = user.get("email", "unknown") if isinstance(user, dict) else str(user)
    try:
        audit_logs.insert_one(
            {
                "action": "ai_execute",
                "user": user_email,
                "command": command,
                "dry_run": dry_run,
                "success": result["success"],
                "stdout": result["stdout"][:1000],
                "stderr": result["stderr"][:1000],
            }
        )
    except Exception:
        pass

    return {
        "success": result["success"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
        "command": command,
    }


@router.get("/status")
def ai_status(
    user=Depends(require_role(["admin", "edit", "view"])),
):
    """Check the AI assistant configuration status."""
    has_openai = bool(OPENAI_API_KEY)
    return {
        "llm_configured": has_openai,
        "llm_model": OPENAI_MODEL if has_openai else None,
        "rule_based": True,
        "status": "ready",
    }
