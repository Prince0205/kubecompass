"""Expose route modules for easier imports from `app.routes`."""

from . import api_resources
from . import api_v1
from . import auth_api
from . import context
from . import crd_resources
from . import deployments
from . import metrics
from . import namespace_requests
from . import network_resources
from . import nodes
from . import pods
from . import replicasets
from . import storage_resources
from . import workloads
from . import config_resources

__all__ = [
    "api_resources",
    "api_v1",
    "auth_api",
    "context",
    "crd_resources",
    "deployments",
    "metrics",
    "namespace_requests",
    "network_resources",
    "nodes",
    "pods",
    "replicasets",
    "storage_resources",
    "workloads",
    "config_resources",
]
