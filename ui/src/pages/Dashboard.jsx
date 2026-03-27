import React, { useState, useEffect } from 'react'
import MetricsChart from '../components/MetricsChart'
import { useAppContext } from '../context/AppContext'
import { metricsAPI } from '../api'
import { clearCache } from '../hooks/useApi'

export default function Dashboard() {
  const { activeCluster, activeNamespace } = useAppContext()
  const [clusterMetrics, setClusterMetrics] = useState(null)
  const [nodeMetrics, setNodeMetrics] = useState([])
  const [namespaceMetrics, setNamespaceMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!activeCluster) return

    const fetchMetrics = async () => {
      setLoading(true)
      setError(null)
      try {
        clearCache('metrics-cluster')
        clearCache('metrics-nodes')
        clearCache(`metrics-namespace-${activeNamespace}`)

        const [clusterRes, nodesRes, nsRes] = await Promise.all([
          metricsAPI.getClusterMetrics(),
          metricsAPI.getNodeMetrics(),
          activeNamespace ? metricsAPI.getNamespaceMetrics(activeNamespace) : Promise.resolve({ data: null })
        ])
        setClusterMetrics(clusterRes.data)
        setNodeMetrics(nodesRes.data || [])
        setNamespaceMetrics(nsRes.data)
      } catch (err) {
        console.error('Error fetching metrics:', err)
        setError(err.response?.data?.detail || 'Failed to load metrics')
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
  }, [activeCluster, activeNamespace])

  const cpuChartData = (nodeMetrics || []).map((node) => ({
    name: node.name || node.node || 'unknown',
    cpu: parseFloat(node.cpu_cores || node.cpu || 0) || 0
  }))

  const memoryChartData = (nodeMetrics || []).map((node) => ({
    name: node.name || node.node || 'unknown',
    memory: parseFloat(node.memory_bytes || node.memory || 0) || 0
  }))

  const formatMemory = (bytes) => {
    if (!bytes) return '0 GB'
    const gb = bytes / (1024 * 1024 * 1024)
    if (gb >= 1) return `${gb.toFixed(2)} GB`
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(2)} MB`
  }

  const formatCPU = (cores) => {
    if (!cores) return '0 cores'
    const num = parseFloat(cores)
    if (num >= 1) {
      return `${num.toFixed(2)} cores`
    } else {
      return `${(num * 1000).toFixed(0)}m`
    }
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">No Cluster Selected</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header to view metrics.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 mt-2">
          Cluster: <span className="text-cyan-400 font-semibold">{activeCluster}</span> | Namespace:{' '}
          <span className="text-cyan-400 font-semibold">{activeNamespace}</span>
        </p>
      </div>

      {loading && (
        <div className="glass-card p-8 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
          <p className="mt-2 text-slate-400">Loading metrics...</p>
        </div>
      )}

      {error && (
        <div className="glass-card p-4 border-red-500/30">
          <p className="text-red-400 font-medium">Error loading metrics</p>
          <p className="text-red-300 text-sm mt-1">{error}</p>
        </div>
      )}

      {clusterMetrics && !loading && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="glass-card p-4">
            <p className="text-slate-400 text-sm">Total CPU</p>
            <p className="text-2xl font-bold text-white mt-1">
              {formatCPU(clusterMetrics.total_cpu_cores || clusterMetrics.total_cpu || 0)}
            </p>
          </div>
          <div className="glass-card p-4">
            <p className="text-slate-400 text-sm">Total Memory</p>
            <p className="text-2xl font-bold text-white mt-1">
              {formatMemory(clusterMetrics.total_memory_bytes || clusterMetrics.total_memory || 0)}
            </p>
          </div>
          <div className="glass-card p-4">
            <p className="text-slate-400 text-sm">Total Nodes</p>
            <p className="text-2xl font-bold text-white mt-1">
              {clusterMetrics.total_nodes || clusterMetrics.node_count || '0'}
            </p>
          </div>
          <div className="glass-card p-4">
            <p className="text-slate-400 text-sm">Total Pods</p>
            <p className="text-2xl font-bold text-white mt-1">
              {clusterMetrics.total_pods || clusterMetrics.pod_count || '0'}
            </p>
          </div>
        </div>
      )}

      {clusterMetrics?.warning && !loading && (
        <div className="glass-card p-4 border-yellow-500/30">
          <p className="text-yellow-400 font-medium">Warning: Metrics Server Not Available</p>
          <p className="text-yellow-300 text-sm mt-1">{clusterMetrics.warning}</p>
        </div>
      )}

      {nodeMetrics.length > 0 && !loading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MetricsChart
            title="CPU Usage by Node"
            type="bar"
            data={cpuChartData}
            dataKey="cpu"
            loading={false}
          />

          <MetricsChart
            title="Memory Usage by Node"
            type="bar"
            data={memoryChartData}
            dataKey="memory"
            loading={false}
          />
        </div>
      )}

      {namespaceMetrics && activeNamespace && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">
            Namespace Usage: {activeNamespace}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center">
              <p className="text-slate-400 text-sm">CPU Used</p>
              <p className="text-xl font-bold text-white mt-2">
                {formatCPU(namespaceMetrics.cpu_used || namespaceMetrics.cpu_cores || 0)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-slate-400 text-sm">Memory Used</p>
              <p className="text-xl font-bold text-white mt-2">
                {formatMemory(namespaceMetrics.memory_used || namespaceMetrics.memory_bytes || 0)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-slate-400 text-sm">Pod Count</p>
              <p className="text-xl font-bold text-white mt-2">
                {namespaceMetrics.pod_count || namespaceMetrics.pods || 0}
              </p>
            </div>
            <div className="text-center">
              <p className="text-slate-400 text-sm">Status</p>
              <p className="text-xl font-bold text-cyan-400 mt-2">Active</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}