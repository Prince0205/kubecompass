# YAML Update Issue Fix - kube-control-plane-other-ai

## Problem Statement

1. **Replica updates work** - Pods scale correctly
2. **Image tags and env variables not persistent** - Even though success message shown after apply
3. **YAML display missing details** - Probes, volume mounts, etc. not shown
4. **Need kubectl edit-like functionality** - Full YAML display and edit as seen in `kubectl get deploy <name> -o yaml`

## Root Cause Analysis

The issue was in the DetailOverlay component where:
1. **YAML was being generated from incomplete data** - The component used the API response data to generate YAML, but this data was incomplete (missing probes, volume mounts, etc.)
2. **No server-side apply was being used** - The old code used `patch` with JSON objects, which doesn't properly handle complex nested fields like environment variables, volume mounts, and probes
3. **UI used wrong API endpoints** - Wasn't using the server-side apply endpoints that properly handle all Kubernetes fields

## Solution Implemented

### 1. Added Full YAML Fetching API

**File: `ui/src/api.js`**
- Added `getResourceYaml` - Fetches full YAML like `kubectl get -o yaml`
- Added `applyResourceYaml` - Uses server-side apply for all resource types

### 2. Updated DetailOverlay to Fetch Full YAML

**File: `ui/src/components/DetailOverlay.jsx`**
- Added new props: `fetchYaml` and `applyYaml`
- On open, fetches full YAML from `/api/resources/{type}/{name}/yaml`
- Uses server-side apply (content-type: `application/apply-patch+yaml`) for all changes
- After apply, refreshes YAML to show actual state

### 3. Updated Resources Page to Pass New Props

**File: `ui/src/pages/Resources.jsx`**
- Imports `v1API`
- Passes `fetchYaml` and `applyYaml` props to DetailOverlay

### 4. Enhanced Backend API Coverage

**File: `app/routes/api_resources.py`**
- Added support for more resource types in YAML fetch:
  - `daemonsets`, `jobs`, `cronjobs`, `ingresses`
- Added corresponding API paths for server-side apply

**File: `app/routes/api_v1.py`**
- Changed all resource types to use server-side apply (PATCH with `application/apply-patch+yaml`)
- Uses `fieldManager=kube-compass` and `force=true` for proper field ownership tracking
- Added support for: `configmaps`, `secrets`, `services`, `pods`, `replicasets`, `jobs`, `cronjobs`, `ingresses`, `pvcs`, `pvs`, `daemonsets`

## How Server-Side Apply Works

Server-side apply is the Kubernetes-native way to apply full YAML manifests:
- Uses `Content-Type: application/apply-patch+yaml`
- Tracks field ownership via `fieldManager`
- Properly handles all fields including:
  - Container images
  - Environment variables
  - Volume mounts
  - Liveness/readiness probes
  - Resource limits
  - And all other Kubernetes fields

## Files Modified

### Frontend
1. `ui/src/api.js` - Added getResourceYaml and applyResourceYaml APIs
2. `ui/src/pages/Resources.jsx` - Pass fetchYaml/applyYaml to DetailOverlay
3. `ui/src/components/DetailOverlay.jsx` - Added full YAML fetching and server-side apply

### Backend
4. `app/routes/api_resources.py` - Extended resource types for YAML fetch and apply
5. `app/routes/api_v1.py` - Changed to server-side apply for all resource types

## Verification

The UI now:
1. ✅ Fetches full YAML like `kubectl get deploy <name> -o yaml` (shows probes, volumes, env vars)
2. ✅ Persists image tag changes
3. ✅ Persists environment variables
4. ✅ Persists volume mounts
5. ✅ Persists liveness/readiness probes
6. ✅ Works for all Kubernetes resource types

This matches the behavior of OpenShift and Lens IDE dashboards.
