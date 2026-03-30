"""
Resource Change Detection Service

Background polling service that automatically detects resource changes
by comparing current state with cached state. Captures snapshots for
ALL changes regardless of source (UI, kubectl, controllers, etc.).
"""

import logging
import threading
import time
from datetime import datetime, timezone

import yaml

from app.db import clusters, resource_history
from app.k8s.loader import load_k8s_client

logger = logging.getLogger(__name__)

# Resource types to watch with their API paths
WATCHABLE_RESOURCES = [
    ("pods", "/api/v1", "namespaced"),
    ("services", "/api/v1", "namespaced"),
    ("configmaps", "/api/v1", "namespaced"),
    ("secrets", "/api/v1", "namespaced"),
    ("deployments", "/apis/apps/v1", "namespaced"),
    ("replicasets", "/apis/apps/v1", "namespaced"),
    ("statefulsets", "/apis/apps/v1", "namespaced"),
    ("daemonsets", "/apis/apps/v1", "namespaced"),
    ("jobs", "/apis/batch/v1", "namespaced"),
    ("cronjobs", "/apis/batch/v1", "namespaced"),
    ("ingresses", "/apis/networking.k8s.io/v1", "namespaced"),
    ("persistentvolumeclaims", "/api/v1", "namespaced"),
    ("horizontalpodautoscalers", "/apis/autoscaling/v2", "namespaced"),
    ("serviceaccounts", "/api/v1", "namespaced"),
    ("persistentvolumes", "/api/v1", "cluster"),
    ("storageclasses", "/apis/storage.k8s.io/v1", "cluster"),
]


class SnapshotService:
    """Background service that detects resource changes via polling."""

    def __init__(self):
        self._cache = {}  # {(cluster_id, namespace, resource_type, name): yaml_hash}
        self._running = False
        self._thread = None
        self._poll_interval = 15  # seconds
        self._watched_namespaces = {}  # {cluster_id: [namespaces]}
        self._last_poll = {}

    def start(self):
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Resource snapshot service started")

    def stop(self):
        """Stop the background polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def notify_namespace(self, cluster_id: str, namespace: str):
        """Register a namespace to watch for a cluster."""
        if cluster_id not in self._watched_namespaces:
            self._watched_namespaces[cluster_id] = set()
        self._watched_namespaces[cluster_id].add(namespace)

    def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            try:
                self._poll_all()
            except Exception as e:
                logger.error(f"Snapshot poll error: {e}", exc_info=True)
            time.sleep(self._poll_interval)

    def _poll_all(self):
        """Poll all watched clusters and namespaces."""
        # Discover clusters from MongoDB
        try:
            all_clusters = list(clusters.find({}, {"_id": 1, "kubeconfig_path": 1}))
        except Exception as e:
            logger.error(f"Failed to fetch clusters: {e}")
            return

        for cluster_doc in all_clusters:
            cluster_id = str(cluster_doc["_id"])
            try:
                kubeconfig = cluster_doc.get("kubeconfig_path")
                if not kubeconfig:
                    continue
                k8s = load_k8s_client(kubeconfig)
                api_client = k8s.ApiClient()
                self._poll_cluster(cluster_id, k8s, api_client)
            except Exception as e:
                logger.debug(f"Snapshot poll failed for cluster {cluster_id}: {e}")

    def _poll_cluster(self, cluster_id: str, k8s, api_client):
        """Poll a single cluster for resource changes."""
        # Get watched namespaces, or default to common ones
        namespaces = self._watched_namespaces.get(cluster_id, set())

        # Always poll default namespace
        namespaces.add("default")

        # Also discover namespaces from the cluster
        try:
            core = k8s.CoreV1Api()
            ns_list = core.list_namespace().items
            for ns in ns_list:
                ns_name = ns.metadata.name
                if ns_name and not ns_name.startswith("kube-"):
                    namespaces.add(ns_name)
        except Exception:
            pass

        self._watched_namespaces[cluster_id] = namespaces

        # Poll namespaced resources
        for resource_type, api_prefix, scope in WATCHABLE_RESOURCES:
            if scope == "namespaced":
                for ns in namespaces:
                    try:
                        self._poll_resource(
                            cluster_id, api_client, resource_type, api_prefix, ns
                        )
                    except Exception as e:
                        logger.debug(f"Poll failed for {resource_type} in {ns}: {e}")
            else:
                try:
                    self._poll_resource(
                        cluster_id, api_client, resource_type, api_prefix, ""
                    )
                except Exception as e:
                    logger.debug(f"Poll failed for {resource_type}: {e}")

    def _extract_meaningful_fields(self, item):
        """Extract only the meaningful fields for change detection.

        Ignores status, managedFields, resourceVersion, uid, timestamps,
        and other transient fields that change on every reconciliation.
        """
        result = {}

        # Metadata: only name, labels, annotations matter
        meta = item.get("metadata", {})
        if meta:
            meaningful_meta = {}
            if meta.get("name"):
                meaningful_meta["name"] = meta["name"]
            if meta.get("labels"):
                meaningful_meta["labels"] = meta["labels"]
            if meta.get("annotations"):
                # Filter out kubectl/managed annotations
                filtered_annotations = {
                    k: v
                    for k, v in meta["annotations"].items()
                    if not k.startswith("kubectl.kubernetes.io/")
                    and not k.startswith("deployment.kubernetes.io/")
                }
                if filtered_annotations:
                    meaningful_meta["annotations"] = filtered_annotations
            if meaningful_meta:
                result["metadata"] = meaningful_meta

        # Spec is the main change detection field
        if item.get("spec"):
            result["spec"] = item["spec"]

        # Data for ConfigMaps and Secrets
        if item.get("data"):
            result["data"] = item["data"]

        # StringData for Secrets
        if item.get("stringData"):
            result["stringData"] = item["stringData"]

        return result

    def _poll_resource(
        self,
        cluster_id: str,
        api_client,
        resource_type: str,
        api_prefix: str,
        namespace: str,
    ):
        """Poll a specific resource type and detect changes."""
        if namespace:
            url = f"{api_client.configuration.host.rstrip('/')}{api_prefix}/namespaces/{namespace}/{resource_type}"
        else:
            url = f"{api_client.configuration.host.rstrip('/')}{api_prefix}/{resource_type}"

        try:
            resp = api_client.rest_client.pool_manager.request(
                "GET", url, headers={"Accept": "application/json"}
            )
            resp_status = resp.status if hasattr(resp, "status") else 200
            if resp_status >= 400:
                return

            resp_bytes = resp.data if hasattr(resp, "data") else resp.read()
            import json

            data = json.loads(resp_bytes.decode("utf-8"))
            items = data.get("items", [])

            for item in items:
                name = item.get("metadata", {}).get("name", "")
                if not name:
                    continue

                # Skip system resources
                if name.startswith("kube-") or namespace.startswith("kube-"):
                    continue

                resource_key = (cluster_id, namespace, resource_type, name)

                # Extract meaningful fields for change detection
                # (ignores status, managedFields, resourceVersion, timestamps, etc.)
                meaningful = self._extract_meaningful_fields(item)
                meaningful_yaml = yaml.safe_dump(meaningful, sort_keys=False)
                meaningful_hash = hash(meaningful_yaml)

                # Full YAML for storage snapshot
                item_yaml = yaml.safe_dump(item, sort_keys=False)

                old_hash = self._cache.get(resource_key)
                if old_hash is not None and old_hash != meaningful_hash:
                    # Meaningful change detected - save snapshot
                    self._save_change_snapshot(
                        cluster_id, namespace, resource_type, name, item_yaml
                    )

                self._cache[resource_key] = meaningful_hash

            # Detect deletions
            current_names = {item.get("metadata", {}).get("name", "") for item in items}
            keys_to_check = [
                k
                for k in list(self._cache.keys())
                if k[0] == cluster_id and k[2] == resource_type and k[1] == namespace
            ]
            for key in keys_to_check:
                if key[3] not in current_names and self._cache.get(key) is not None:
                    # Resource was deleted
                    self._save_delete_snapshot(
                        cluster_id, namespace, resource_type, key[3]
                    )
                    del self._cache[key]

        except Exception as e:
            logger.debug(f"Failed to poll {resource_type}/{namespace}: {e}")

    def _save_change_snapshot(
        self,
        cluster_id: str,
        namespace: str,
        resource_type: str,
        name: str,
        current_yaml: str,
    ):
        """Save a snapshot for a detected change."""
        try:
            # Map resource_type to the names used in the rest of the app
            type_mapping = {
                "persistentvolumeclaims": "pvcs",
                "persistentvolumes": "pvs",
                "horizontalpodautoscalers": "hpas",
            }
            mapped_type = type_mapping.get(resource_type, resource_type)

            doc = {
                "resource_type": mapped_type,
                "resource_name": name,
                "namespace": namespace,
                "cluster_id": cluster_id,
                "operation": "apply",
                "user": "system",
                "yaml_before": None,
                "yaml_after": current_yaml,
                "timestamp": datetime.now(timezone.utc),
            }
            resource_history.insert_one(doc)
            logger.info(
                f"Auto-detected change: {mapped_type}/{name} in {namespace or 'cluster'}"
            )
        except Exception as e:
            logger.error(f"Failed to save auto-detected snapshot: {e}")

    def _save_delete_snapshot(
        self, cluster_id: str, namespace: str, resource_type: str, name: str
    ):
        """Save a snapshot for a detected deletion."""
        try:
            type_mapping = {
                "persistentvolumeclaims": "pvcs",
                "persistentvolumes": "pvs",
                "horizontalpodautoscalers": "hpas",
            }
            mapped_type = type_mapping.get(resource_type, resource_type)

            doc = {
                "resource_type": mapped_type,
                "resource_name": name,
                "namespace": namespace,
                "cluster_id": cluster_id,
                "operation": "delete",
                "user": "system",
                "yaml_before": None,
                "yaml_after": None,
                "timestamp": datetime.now(timezone.utc),
            }
            resource_history.insert_one(doc)
            logger.info(
                f"Auto-detected deletion: {mapped_type}/{name} in {namespace or 'cluster'}"
            )
        except Exception as e:
            logger.error(f"Failed to save auto-detected delete snapshot: {e}")


# Global singleton
snapshot_service = SnapshotService()
