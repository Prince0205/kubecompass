# Kube Compass - UI Fixes Summary

## Issues Fixed

### Issue 1: Metrics Not Loading in UI
**Problem:** Dashboard was showing 0 cores, 0 GB, and "Metrics Server Not Available" warning even when metrics were available.

**Root Cause:**
- Cache was not being invalidated when dependencies changed
- The memory hook wasn't properly tracking when to refetch metrics

**Solution:**
- Added `clearCache()` calls in Dashboard.jsx when fetching metrics
- Imported `clearCache` function from useApi hook
- Added cache clearing for cluster metrics, node metrics, and namespace metrics before each fetch

**Files Modified:**
- `ui/src/pages/Dashboard.jsx` - Added cache clearing on metrics fetch

---

### Issue 2: Namespace Dropdown Not Updating Resources Instantly (Multi-reload Required)
**Problem:** When selecting a different namespace from the dropdown, resources list wouldn't update immediately. Users had to reload the browser several times to see changes.

**Root Causes:**
1. **Broken dependency tracking in useApi hook** - The useFetchList hook had a flawed custom dependency tracking system using JSON.stringify that was unreliable
2. **Spread operator in dependencies array** - Using `...dependencies` in the useEffect was problematic because it unpredictably included values that might be recreated each render
3. **Race condition with async namespace sync** - The AppContext was not awaiting the backend namespace context update before components made API calls
4. **Missing activeNamespace in direct dependencies** - The useEffect needed direct access to activeCluster and activeNamespace for proper React dependency tracking

**Solutions:**
1. **Fixed useFetchList hook** (`ui/src/hooks/useApi.js`):
   - Removed broken `prevDependencies` ref and JSON.stringify comparison logic
   - Removed the spread operator pattern from useEffect dependencies
   - Added `activeCluster` and `activeNamespace` directly to the dependency array
   - Now properly clears cache when cluster or namespace changes
   - Dependencies are now: `[fetchData, cacheKey, activeCluster, activeNamespace]`

2. **Fixed AppContext selectNamespace** (`ui/src/context/AppContext.jsx`):
   - Changed `selectNamespace` from synchronous to async
   - Now awaits the axios POST to `/v1/context/namespace` before returning
   - This ensures backend context is updated before components make API calls
   - Eliminates race condition where components would use old namespace

3. **Added cache clearing to Dashboard** (`ui/src/pages/Dashboard.jsx`):
   - Explicitly clear metrics cache before fetching
   - Ensures fresh data on every fetch, especially on namespace change

**Files Modified:**
- `ui/src/hooks/useApi.js` - Fixed useFetchList dependency tracking
- `ui/src/context/AppContext.jsx` - Made selectNamespace async and awaited
- `ui/src/pages/Dashboard.jsx` - Added cache clearing on fetch

---

## How The Fixes Work

### Namespace Update Flow (Before vs After)

**BEFORE (Broken):**
1. User selects namespace "test" in dropdown
2. selectNamespace() called (not awaited)
3. Component sees new activeNamespace immediately
4. useFetchList hook's dependencies might not trigger properly due to broken JSON.stringify logic
5. OR even if hook triggers, backend still has old namespace
6. API returns data for old namespace
7. User sees old data or nothing

**AFTER (Fixed):**
1. User selects namespace "test" in dropdown
2. selectNamespace() called and awaited
3. axios POST waits for backend to update namespace context
4. THEN component's activeNamespace state updates
5. useFetchList hook detects activeNamespace change in dependencies
6. Cache is cleared (no broken logic)
7. API call is made with updated backend namespace context
8. Fresh data for new namespace is returned immediately
9. UI updates instantly

### Cache Invalidation Flow (Before vs After)

**BEFORE (Broken):**
```javascript
const depsChanged = JSON.stringify(dependencies) !== JSON.stringify(prevDependencies.current)
if (depsChanged) {
  cache.delete(cacheKey)
  prevDependencies.current = dependencies
}
// But dependencies is recreated each render!
// So comparison might fail...
```

**AFTER (Fixed):**
```javascript
useEffect(() => {
  isMounted.current = true
  // Direct cache clearing - no complex logic
  cache.delete(cacheKey)
  fetchData()

  return () => {
    isMounted.current = false
  }
  // Direct dependency tracking - React handles this
}, [fetchData, cacheKey, activeCluster, activeNamespace])
```

---

## Test Results

✅ **80 tests PASSED** (including all resource API tests)
⚠️ **2 tests FAILED** (pre-existing metrics mock setup issues, not related to these fixes)

Backend API changes: None required
Frontend changes: 3 files modified

---

## Verification Steps

### To test the fixes:

1. **Test Namespace Updates:**
   - Open the application
   - Select a cluster
   - View resources in default namespace
   - Change namespace dropdown to another namespace (e.g., "kube-system")
   - **Expected:** Resources update immediately, no reload required

2. **Test Metrics Loading:**
   - Navigate to Dashboard page
   - **Expected:** Metrics are loaded and displayed
   - Change namespace
   - **Expected:** Metrics update to new namespace immediately

3. **Test Multiple Namespace Switches:**
   - Change namespace back and forth rapidly
   - **Expected:** No errors, data always reflects current namespace

---

## Files Modified

1. `ui/src/hooks/useApi.js` - Fixed dependency tracking in useFetchList
2. `ui/src/context/AppContext.jsx` - Made namespace sync async
3. `ui/src/pages/Dashboard.jsx` - Added cache clearing for metrics

All changes are backward compatible and don't require any API changes.
