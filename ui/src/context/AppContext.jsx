/**
 * AppContext - Global state management for the application
 * Manages: user auth, active cluster, active namespace, theme
 * Integrates with backend MongoDB for cluster/namespace data
 */

import React, { createContext, useState, useCallback, useEffect } from 'react'
import axios from 'axios'

export const AppContext = createContext()

// Cluster-scoped resources that don't need a namespace
const CLUSTER_SCOPED_RESOURCES = [
  'clusterroles',
  'clusterrolebindings',
  'nodes',
  'persistentvolumes',
  'storageclasses',
]

export const AppProvider = ({ children }) => {
  const [auth, setAuth] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [initialized, setInitialized] = useState(false)
  const [activeCluster, setActiveCluster] = useState(localStorage.getItem('activeCluster') || null)
  const [activeNamespace, setActiveNamespace] = useState(localStorage.getItem('activeNamespace') || 'default')
  const [clusters, setClusters] = useState([])
  const [namespaces, setNamespaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isClusterScoped, setIsClusterScoped] = useState(false)
  const [lastNamespacedNamespace, setLastNamespacedNamespace] = useState(() => 
    localStorage.getItem('lastNamespacedNamespace') || 'default'
  )

  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await axios.get('/api/auth/me', {
          withCredentials: true
        })
        if (response.data.authenticated) {
          setAuth(response.data.user)
        } else {
          setAuth(null)
        }
      } catch (err) {
        console.error('Error checking auth:', err)
        setAuth(null)
      } finally {
        setAuthLoading(false)
      }
    }

    checkAuth()
  }, [])

  // Track if initial load is complete
  const [initialLoadComplete, setInitialLoadComplete] = useState(false)

  // Fetch clusters from MongoDB on mount (only if authenticated)
  useEffect(() => {
    if (!auth) return

    const fetchClusters = async () => {
      try {
        setLoading(true)
        const response = await axios.get('/v1/clusters', {
          withCredentials: true
        })
        const clusterList = response.data || []
        setClusters(clusterList)

        // If no cluster selected or selected cluster not found, select first
        if (clusterList.length > 0) {
          const savedClusterId = localStorage.getItem('activeCluster')
          const clusterExists = clusterList.find(c => c.id === savedClusterId)

          let clusterToUse = activeCluster || savedClusterId
          
          if (!clusterToUse || !clusterExists) {
            clusterToUse = clusterList[0].id
          }

          // Set context on backend FIRST, then update local state
          // This prevents race condition where fetchNamespaces fires before context is set
          try {
            await axios.post('/v1/context/cluster', { cluster_id: clusterToUse }, {
              withCredentials: true
            })
            await axios.post('/v1/context/namespace', { namespace: 'default' }, {
              withCredentials: true
            })
          } catch (err) {
            console.error('Error setting cluster context:', err)
          }

          setActiveCluster(clusterToUse)
          setActiveNamespace('default')
          localStorage.setItem('activeCluster', clusterToUse)
          localStorage.setItem('activeNamespace', 'default')
        }
        setError(null)
        setInitialized(true)
      } catch (err) {
        console.error('Error fetching clusters:', err)
        setError('Failed to load clusters')
        setInitialized(true)
      } finally {
        setLoading(false)
      }
    }

    fetchClusters()
  }, [auth])

  // Fetch namespaces when cluster changes
  useEffect(() => {
    const fetchNamespaces = async () => {
      if (!activeCluster) {
        setNamespaces([])
        return
      }

      try {
        const response = await axios.get('/v1/namespaces', {
          withCredentials: true
        })
        const nsList = response.data || []
        setNamespaces(nsList)
        
        // Sync namespace with backend
        const savedNamespace = localStorage.getItem('activeNamespace') || 'default'
        // Don't send _all to backend - use special marker
        const backendNamespace = savedNamespace === '_all' ? '_all_' : savedNamespace
        try {
          await axios.post('/v1/context/namespace', { namespace: backendNamespace }, {
            withCredentials: true
          })
        } catch (err) {
          console.error('Error setting namespace context:', err)
        }
      } catch (err) {
        console.error('Error fetching namespaces:', err)
        setNamespaces([{ name: 'default' }])
      }
    }

    fetchNamespaces()
  }, [activeCluster])

  // Persist cluster and namespace to localStorage
  useEffect(() => {
    if (activeCluster) localStorage.setItem('activeCluster', activeCluster)
  }, [activeCluster])

  useEffect(() => {
    localStorage.setItem('activeNamespace', activeNamespace)
  }, [activeNamespace])

  // Update active cluster and set context on backend
  const selectCluster = useCallback(async (clusterId) => {
    setError(null)

    // Set context on backend FIRST
    try {
      await axios.post('/v1/context/cluster', { cluster_id: clusterId }, {
        withCredentials: true
      })
      // THEN update local state after backend is confirmed
      setActiveCluster(clusterId)
      setActiveNamespace('default')
    } catch (err) {
      console.error('Error setting cluster context:', err)
    }
  }, [])

  // Update active namespace and set context on backend
  const selectNamespace = useCallback(async (namespace) => {
    setError(null)

    // Check if switching to cluster-scoped mode (All namespaces)
    if (namespace === '_all') {
      // Save current namespaced namespace before switching
      if (activeNamespace && activeNamespace !== '_all') {
        setLastNamespacedNamespace(activeNamespace)
        localStorage.setItem('lastNamespacedNamespace', activeNamespace)
      }
      setIsClusterScoped(true)
      setActiveNamespace('_all')
      try {
        await axios.post('/v1/context/namespace', { namespace: '_all_' }, {
          withCredentials: true
        })
      } catch (err) {
        console.error('Error setting namespace context:', err)
      }
      return
    }

    // Normal namespace selection
    setIsClusterScoped(false)
    try {
      await axios.post('/v1/context/namespace', { namespace }, {
        withCredentials: true
      })
      setActiveNamespace(namespace)
    } catch (err) {
      console.error('Error setting namespace context:', err)
    }
  }, [activeNamespace, lastNamespacedNamespace])

  // Set cluster-scoped mode (for cluster-scoped resources)
  const setClusterScoped = useCallback(async (scoped) => {
    if (scoped) {
      // Save current namespaced namespace before switching
      if (activeNamespace && activeNamespace !== '_all') {
        setLastNamespacedNamespace(activeNamespace)
        localStorage.setItem('lastNamespacedNamespace', activeNamespace)
      }
      setIsClusterScoped(true)
      setActiveNamespace('_all')
      try {
        await axios.post('/v1/context/namespace', { namespace: '_all_' }, {
          withCredentials: true
        })
      } catch (err) {
        console.error('Error setting cluster-scoped context:', err)
      }
    } else {
      // Restore last used namespace
      setIsClusterScoped(false)
      const namespaceToRestore = lastNamespacedNamespace || 'default'
      setActiveNamespace(namespaceToRestore)
      try {
        await axios.post('/v1/context/namespace', { namespace: namespaceToRestore }, {
          withCredentials: true
        })
      } catch (err) {
        console.error('Error restoring namespace context:', err)
      }
    }
  }, [activeNamespace, lastNamespacedNamespace])

  // Check if a resource type is cluster-scoped
  const isResourceClusterScoped = useCallback((resourceType) => {
    return CLUSTER_SCOPED_RESOURCES.includes(resourceType)
  }, [])

  // Logout
  const logout = useCallback(async () => {
    try {
      await axios.post('/api/auth/logout', {}, {
        withCredentials: true
      })
      setAuth(null)
      setActiveCluster(null)
      setActiveNamespace('default')
      localStorage.removeItem('activeCluster')
      localStorage.removeItem('activeNamespace')
    } catch (err) {
      console.error('Error logging out:', err)
    }
  }, [])

  // Set loading state
  const setIsLoading = useCallback((isLoading) => {
    setLoading(isLoading)
  }, [])

  // Set error message
  const setErrorMessage = useCallback((message) => {
    setError(message)
  }, [])

  // Clear error
  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const value = {
    // Auth state
    auth,
    setAuth,
    authLoading,
    logout,

    // Initialization state
    initialized,

    // Cluster/Namespace state
    activeCluster,
    activeNamespace,
    selectCluster,
    selectNamespace,
    setClusterScoped,
    isResourceClusterScoped,
    isClusterScoped,
    lastNamespacedNamespace,

    // Data state
    clusters,
    setClusters,
    namespaces,
    setNamespaces,

    // UI state
    loading,
    setIsLoading,
    error,
    setErrorMessage,
    clearError,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useAppContext = () => {
  const context = React.useContext(AppContext)
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider')
  }
  return context
}
