# KubeCompass - Feature Roadmap & Competitive Analysis

**Date:** 2026-03-27
**Status:** Strategic Planning Document

---

## Market Context (2026)

The timing is perfect for KubeCompass to dominate the Kubernetes dashboard space:

- **OpenLens** is dead/unmaintained (last update was months ago)
- **Kubernetes Dashboard** is officially sunset and being archived
- **OpenShift Console** is proprietary, complex, and OpenShift-only
- There is a massive vacuum in the open-source, multi-cluster K8s dashboard space

---

## Current Strengths to Build On

The codebase already has a solid foundation:

- Multi-cluster support with session-based context
- RBAC with 3 roles (admin/edit/view)
- Server-side YAML apply (like `kubectl apply`)
- Generic resource CRUD for 25+ resource types
- Namespace provisioning workflow with approvals
- React SPA with Tailwind, Vite, Recharts
- FastAPI backend with MongoDB persistence

---

## 10 Feature Recommendations (Prioritized by Impact x Feasibility)

### 1. AI-Powered Kubernetes Assistant (HIGHEST DIFFERENTIATOR)

**What:** Natural language interface for Kubernetes operations. No competitor has this.

```
User: "Why is my nginx pod in CrashLoopBackOff?"
AI:   "Pod 'nginx-7d4b8c6f9-xk2lm' is crashing because:
       - OOMKilled: container used 512Mi but limit is 256Mi
       - Last 3 restarts: 2 min ago, 8 min ago, 15 min ago
       Suggested fix: Increase memory limit to 512Mi"
       [Apply Fix] button
```

**Implementation:**
- New file: `app/routes/ai_assistant.py`
- New file: `ui/src/pages/Assistant.jsx`
- Integrate OpenAI/Anthropic API (user provides their own key)
- Feed pod logs, events, resource status as context
- Support: explain errors, suggest fixes, generate YAML, optimize resources, security audit

**Why unique:** Neither OpenLens nor OpenShift has an AI assistant. This alone could be the #1 reason people choose KubeCompass.

---

### 2. Interactive Topology / Dependency Graph

**What:** Visual graph showing how resources relate to each other — like OpenShift's topology view but for vanilla Kubernetes.

```
[Deployment: nginx] ──owns──> [ReplicaSet: nginx-7d4b] ──owns──> [Pod: nginx-7d4b-xk2lm]
      │
      ├──selector──> [Service: nginx-svc] ──ingress──> [Ingress: nginx-ingress]
      │
      └──mounts──> [ConfigMap: nginx-conf] + [Secret: nginx-tls]
```

**Implementation:**
- New file: `app/routes/topology.py` — builds graph by traversing ownerReferences, selectors, volumes
- New file: `ui/src/pages/Topology.jsx` — uses React Flow or D3.js for interactive graph
- Backend traverses: Deployment → ReplicaSet → Pods, Service → Endpoints → Pods, PVC → PV
- Click any node to open existing DetailOverlay
- Real-time status colors (green=running, red=error, yellow=pending)

**Why unique:** OpenLens has no topology view. OpenShift's is limited to Developer perspective and OpenShift-specific resources.

---

### 3. Cost Analysis & Right-Sizing Engine

**What:** Estimate cloud costs per resource, namespace, and label. Recommend right-sizing based on actual usage vs requested resources.

**Implementation:**
- New file: `app/routes/cost_analyzer.py`
- New file: `ui/src/pages/CostAnalysis.jsx`
- Use K8s Metrics API (already integrated) for actual usage
- User configures cloud pricing (e.g., $0.04/vCPU/hour, $0.005/GB/hour)
- Show: cost per namespace, cost per workload, idle resource waste
- Right-sizing recommendations: "nginx deployment requests 2 CPU but uses 0.1 CPU. Reduce to 0.25 CPU to save $X/month"
- Export cost reports as CSV

**Why unique:** OpenLens shows metrics but never calculates costs. OpenShift has cost management but it's a separate, complex product (OpenShift Cost Management / Kubecost integration).

---

### 4. Real-Time Event Stream & Alerting

**What:** Live WebSocket feed of cluster events with configurable alert rules.

**Implementation:**
- New file: `app/routes/events_stream.py` — WebSocket endpoint for real-time events
- New file: `app/routes/alerts.py` — CRUD for alert rules stored in MongoDB
- New file: `ui/src/pages/Events.jsx` — live event stream with filtering
- New file: `ui/src/pages/Alerts.jsx` — configure alert rules
- Alert rules: "Notify when any pod OOMKills", "Alert when node NotReady > 5min"
- Notification channels: in-app, webhook, email (SMTP)
- Event correlation: group related events (e.g., pod crash → replicaset scaling → deployment update)

**Why unique:** OpenLens has no alerting. OpenShift requires Prometheus/Alertmanager setup. This is built-in and zero-config.

---

### 5. Time-Travel Debugging (Resource History)

**What:** Track resource changes over time. See what changed, when, and by whom. Replay previous states.

**Implementation:**
- New file: `app/routes/history.py`
- New file: `ui/src/pages/History.jsx`
- On every mutation (create/update/delete), snapshot the resource YAML to MongoDB
- Timeline view: shows changes chronologically
- Diff view: side-by-side comparison of any two snapshots
- "Restore" button: re-apply a previous YAML version
- Correlate with audit logs (already implemented for node operations)

**Why unique:** Neither OpenLens nor OpenShift has a built-in time-travel debugger. `kubectl` has no history command. This is extremely valuable for post-incident analysis.

---

### 6. Compliance & Security Scanner

**What:** One-click security and compliance scanning of the entire cluster.

**Implementation:**
- New file: `app/routes/security.py`
- New file: `ui/src/pages/Security.jsx`
- Built-in checks (no external tools needed):
  - Pods running as root
  - Privileged containers
  - Containers without resource limits
  - Secrets used as environment variables
  - Services without NetworkPolicies
  - RBAC over-permissioned (cluster-admin bindings)
  - Images from untrusted registries
  - Missing PodDisruptionBudgets
  - Nodes running outdated Kubernetes versions
- Scoring: 0-100 security score per namespace and cluster
- CIS Kubernetes Benchmark checks (subset)
- RBAC analyzer: "User X has admin role but only needs view" (inverse of least-privilege)

**Why unique:** OpenLens has no security scanning. OpenShift has SCC (Security Context Constraints) but no unified security dashboard. Third-party tools like Trivy/Polaris require separate installation.

---

### 7. Multi-Cluster Comparison View

**What:** Side-by-side comparison of the same resource/namespace across clusters. Detect configuration drift.

**Implementation:**
- New file: `ui/src/pages/Compare.jsx`
- Select 2+ clusters, select resource type
- Show resources side-by-side with diff highlighting
- "Sync" button: apply resource from cluster A to cluster B
- Drift detection: automatically flag when the same deployment differs between clusters

**Why unique:** OpenLens manages multiple clusters but has no comparison view. OpenShift is single-cluster. This is critical for multi-environment (dev/staging/prod) management.

---

### 8. Custom Dashboard Builder

**What:** Let users build their own dashboard views by dragging and dropping widgets.

**Implementation:**
- New file: `app/routes/dashboards.py` — CRUD for custom dashboards (stored in MongoDB)
- New file: `ui/src/pages/CustomDashboard.jsx` — drag-and-drop canvas
- Widget types: metric card, resource list, chart, event feed, YAML preview, status indicator
- Each widget: configurable resource type, namespace, refresh interval
- Share dashboards across team (stored per-user or shared)
- Pre-built templates: "SRE Overview", "Developer Workspace", "Cost Watch"

**Why unique:** OpenLens has a fixed dashboard. OpenShift has limited customization. This makes the tool adapt to each team's workflow.

---

### 9. Helm Chart Manager

**What:** Browse, install, upgrade, and rollback Helm releases from the UI.

**Implementation:**
- New file: `app/routes/helm.py` — uses `subprocess` to run `helm` CLI or `pyhelm` library
- New file: `ui/src/pages/Helm.jsx`
- List installed releases with status, chart version, app version
- Browse Helm repositories (add/remove repos)
- Install chart with values editor
- Upgrade/downgrade releases
- Rollback to previous revision
- Show release history with diff

**Why unique:** OpenLens had basic Helm support via extensions but it was broken. OpenShift uses Operators instead of Helm. Native Helm management in a web dashboard is rare.

---

### 10. Collaborative Operations (Team Features)

**What:** Real-time collaboration features for SRE/DevOps teams.

**Implementation:**
- WebSocket-based presence: see who else is viewing the same resource
- Change approval workflow: "User X wants to scale deployment Y to 10 replicas — Approve/Reject"
- Shared notes on resources: attach notes to any resource (visible to team)
- Activity feed: "User X viewed pod logs for nginx", "User Y scaled deployment api to 5 replicas"
- Extend existing audit_logs to power the activity feed

**Why unique:** No Kubernetes dashboard has real-time collaboration. This transforms KubeCompass from a tool into a platform.

---

## Recommended Implementation Order

| Phase | Features | Effort | Impact |
|-------|----------|--------|--------|
| **Phase 1** (Quick Wins) | #6 Security Scanner, #5 Resource History, #3 Cost Analysis | Medium | High |
| **Phase 2** (Core Differentiators) | #2 Topology Graph, #4 Real-Time Events, #8 Custom Dashboards | High | Very High |
| **Phase 3** (Power Features) | #1 AI Assistant, #7 Multi-Cluster Compare, #9 Helm Manager | High | Very High |
| **Phase 4** (Platform Play) | #10 Collaborative Operations | Very High | High |

---

## Competitive Positioning Matrix

| Feature                 | KubeCompass | OpenLens | OpenShift | K8s Dashboard |
|-------------------------|-------------|----------|-----------|---------------|
| Multi-cluster           |     Yes     |   Yes    |    No     |      No       |
| AI Assistant            |     Yes     |   No     |    No     |      No       |
| Topology View           |     Yes     |   No     |    Yes*   |      No       |
| Cost Analysis           |     Yes     |   No     |    Yes**  |      No       |
| Real-Time Alerting      |     Yes     |   No     |    Part   |      No       |
| Time-Travel Debug       |     Yes     |   No     |    No     |      No       |
| Security Scanning       |     Yes     |   No     |    Part   |      No       |
| Cluster Comparison      |     Yes     |   No     |    No     |      No       |
| Custom Dashboards       |     Yes     |   No     |    No     |      No       |
| Helm Management         |     Yes     |   Part   |    No     |      No       |
| Collaboration           |     Yes     |   No     |    No     |      No       |
| Open Source             |     Yes     |   No     |    No     |      Yes      |
| Vanilla K8s Support     |     Yes     |   Yes    |    No     |      Yes      |

Legend:
- Yes = Full support
- No = Not available
- Part = Partial or broken support
- * = OpenShift only, limited to Developer perspective
- ** = Requires separate Cost Management product (Kubecost integration)
- Part (Real-Time Alerting) = Requires separate Prometheus/Alertmanager setup

---

## Key Differentiators Summary

KubeCompass would be the **only** open-source dashboard that combines all of these capabilities in a single, easy-to-install package:

1. **AI-native** — No competitor has a built-in AI assistant for Kubernetes operations
2. **Zero-dependency security scanning** — Built-in, no external tools required
3. **Time-travel debugging** — Unique capability not found in any competitor
4. **Multi-cluster diff & sync** — Critical for multi-environment workflows
5. **Cost awareness** — First open-source dashboard with built-in cost estimation
6. **Team collaboration** — Transforms from tool to platform
7. **Web-based** — No desktop app required (unlike OpenLens)
8. **Vanilla K8s** — Works with any Kubernetes distribution (unlike OpenShift)
9. **Active development** — Unlike dead projects (OpenLens, K8s Dashboard)
