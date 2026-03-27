"""Expose route modules for easier imports from `app.routes`.

This file imports individual route modules so callers can do
`from app.routes import auth, dashboard, ...` as the project expects.
"""

from . import auth
from . import dashboard
from . import namespace
from . import clusters
from . import admin
from . import resources
from . import api_resources
from . import context
from . import nodes
from . import cluster_overview
from . import ui_cluster
from . import pods
from . import deployments
from . import replicasets
from . import resource_page
from . import namespace_requests
from . import metrics
from . import workloads
from . import config_resources
from . import network_resources
from . import storage_resources
from . import crd_resources
from . import api_v1
from . import auth_api

__all__ = [
    "auth",
    "dashboard",
    "namespace",
    "clusters",
    "admin",
    "resources",
    "api_resources",
    "context",
    "nodes",
    "cluster_overview",
    "ui_cluster",
    "pods",
    "deployments",
    "replicasets",
    "resource_page",
    "namespace_requests",
    "metrics",
    "workloads",
    "config_resources",
    "network_resources",
    "storage_resources",
    "crd_resources",
    "api_v1",
    "auth_api",
]
