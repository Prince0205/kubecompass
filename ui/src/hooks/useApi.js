/**
 * Custom hooks for data fetching and API interactions
 * Provides caching, error handling, and loading states
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAppContext } from '../context/AppContext'
import apiClient from '../api'

// Simple in-memory cache with TTL
const cache = new Map()
const CACHE_TTL = 60000 // 60 seconds

const getCachedData = (key) => {
  const item = cache.get(key)
  if (!item) return null
  if (Date.now() - item.timestamp > CACHE_TTL) {
    cache.delete(key)
    return null
  }
  return item.data
}

const setCachedData = (key, data) => {
  cache.set(key, { data, timestamp: Date.now() })
}

/**
 * Hook for fetching list data from API
 * @param {Function} apiCall - API function to call
 * @param {string} cacheKey - Unique cache key for this data
 * @param {Array} dependencies - Re-fetch when these change
 * @param {any} triggerKey - Additional key to trigger fresh fetch
 */
export const useFetchList = (apiCall, cacheKey, dependencies = [], triggerKey) => {
  const { setIsLoading, setErrorMessage, activeCluster, activeNamespace } = useAppContext()
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const isMounted = useRef(true)
  const triggerRef = useRef(0)
  const apiCallRef = useRef(apiCall)

  // Always keep the latest apiCall without causing re-renders
  apiCallRef.current = apiCall

  const fetchData = useCallback(async () => {
    if (!activeCluster) {
      setError('No cluster selected')
      return
    }

    setLoading(true)
    setError(null)
    setIsLoading(true)

    try {
      const response = await apiCallRef.current()
      if (isMounted.current) {
        // Extract items from response - handle both array and object formats
        let items = []
        if (Array.isArray(response.data)) {
          items = response.data
        } else if (response.data && typeof response.data === 'object') {
          // Get first key's value if it's an object
          const firstKey = Object.keys(response.data)[0]
          items = response.data[firstKey] || []
        }
        setData(items)
        setCachedData(cacheKey, items)
      }
    } catch (err) {
      if (isMounted.current) {
        const message = err.response?.data?.detail || err.message || 'Failed to fetch data'
        setError(message)
        setErrorMessage(message)
      }
    } finally {
      if (isMounted.current) {
        setLoading(false)
        setIsLoading(false)
      }
    }
  }, [cacheKey, activeCluster, activeNamespace, setIsLoading, setErrorMessage])

  useEffect(() => {
    isMounted.current = true
    // Always clear cache and fetch fresh data when cacheKey or activeCluster/activeNamespace change
    cache.delete(cacheKey)
    triggerRef.current += 1
    fetchData()

    return () => {
      isMounted.current = false
    }
    // Use activeCluster and activeNamespace directly instead of spreading dependencies
    // Add triggerRef.current to dependencies to force refetch when triggerKey changes
  }, [fetchData, cacheKey, activeCluster, activeNamespace, triggerRef.current])

  // Additional effect to handle triggerKey changes separately
  useEffect(() => {
    if (triggerKey !== undefined) {
      cache.delete(cacheKey)
      triggerRef.current += 1
      fetchData()
    }
  }, [triggerKey])


  return { data, loading, error, refetch: fetchData }
}

/**
 * Hook for fetching detail data from API
 * @param {Function} apiCall - API function to call
 * @param {string} cacheKey - Unique cache key for this data
 */
export const useFetchDetail = (apiCall, cacheKey) => {
  const { setIsLoading, setErrorMessage, activeCluster } = useAppContext()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const isMounted = useRef(true)
  const apiCallRef = useRef(apiCall)

  // Always keep the latest apiCall without causing re-renders
  apiCallRef.current = apiCall

  const fetchData = useCallback(async () => {
    if (!activeCluster) {
      setError('No cluster selected')
      return
    }

    // Check cache first
    const cached = getCachedData(cacheKey)
    if (cached) {
      setData(cached)
      return
    }

    setLoading(true)
    setError(null)
    setIsLoading(true)

    try {
      const response = await apiCallRef.current()
      if (isMounted.current) {
        setData(response.data)
        setCachedData(cacheKey, response.data)
      }
    } catch (err) {
      if (isMounted.current) {
        const message = err.response?.data?.detail || err.message || 'Failed to fetch data'
        setError(message)
        setErrorMessage(message)
      }
    } finally {
      if (isMounted.current) {
        setLoading(false)
        setIsLoading(false)
      }
    }
  }, [cacheKey, activeCluster, setIsLoading, setErrorMessage])

  useEffect(() => {
    isMounted.current = true
    fetchData()

    return () => {
      isMounted.current = false
    }
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

/**
 * Hook for mutations (POST, PUT, DELETE)
 */
export const useMutation = () => {
  const { setIsLoading, setErrorMessage } = useAppContext()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const mutate = useCallback(async (apiCall) => {
    setLoading(true)
    setError(null)
    setIsLoading(true)

    try {
      const response = await apiCall()
      return response.data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Operation failed'
      setError(message)
      setErrorMessage(message)
      throw err
    } finally {
      setLoading(false)
      setIsLoading(false)
    }
  }, [setIsLoading, setErrorMessage])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  return { mutate, loading, error, clearError }
}

/**
 * Hook for polling data at intervals
 */
export const usePoll = (apiCall, cacheKey, interval = 5000, dependencies = []) => {
  const { data, loading, error, refetch } = useFetchList(apiCall, cacheKey, dependencies)
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true

    const timer = setInterval(() => {
      if (isMounted.current) {
        refetch()
      }
    }, interval)

    return () => {
      isMounted.current = false
      clearInterval(timer)
    }
  }, [refetch, interval])

  return { data, loading, error, refetch }
}

/**
 * Clear cache for a specific key
 */
export const clearCache = (key) => {
  cache.delete(key)
}

/**
 * Clear all cache
 */
export const clearAllCache = () => {
  cache.clear()
}
