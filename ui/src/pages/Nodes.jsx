/**
 * Nodes Page
 * Displays cluster nodes with their status and details
 */

import React, { useState, useEffect } from 'react'
import { useAppContext } from '../context/AppContext'
import { nodesAPI } from '../api'
import DetailOverlay from '../components/DetailOverlay'
import apiClient from '../api'

export default function Nodes() {
  const { activeCluster } = useAppContext()
  const [selectedNode, setSelectedNode] = useState(null)
  const [showDetail, setShowDetail] = useState(false)
  const [actionLoading, setActionLoading] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [nodeDetail, setNodeDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    if (!activeCluster) {
      setNodes([])
      return
    }

    const fetchNodes = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await nodesAPI.listNodes()
        setNodes(response.data || [])
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load nodes')
      } finally {
        setLoading(false)
      }
    }

    fetchNodes()
  }, [activeCluster])

  useEffect(() => {
    if (!selectedNode) {
      setNodeDetail(null)
      return
    }

    const fetchNodeDetail = async () => {
      setDetailLoading(true)
      try {
        const response = await nodesAPI.getNode(selectedNode.name)
        setNodeDetail(response.data)
      } catch (err) {
        console.error('Error fetching node detail:', err)
      } finally {
        setDetailLoading(false)
      }
    }

    fetchNodeDetail()
  }, [selectedNode])

  const refetch = async () => {
    if (!activeCluster) return
    setLoading(true)
    try {
      const response = await nodesAPI.listNodes()
      setNodes(response.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load nodes')
    } finally {
      setLoading(false)
    }
  }

  const handleNodeClick = (node) => {
    setSelectedNode(node)
    setShowDetail(true)
  }

  const handleCordon = async (nodeName) => {
    setActionLoading('cordon')
    setActionError(null)
    try {
      await nodesAPI.cordonNode(nodeName)
      refetch()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to cordon node')
    } finally {
      setActionLoading(null)
    }
  }

  const handleUncordon = async (nodeName) => {
    setActionLoading('uncordon')
    setActionError(null)
    try {
      await nodesAPI.uncordonNode(nodeName)
      refetch()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to uncordon node')
    } finally {
      setActionLoading(null)
    }
  }

  const handleDrain = async (nodeName) => {
    if (!confirm(`Are you sure you want to drain node ${nodeName}? This will evict all pods.`)) {
      return
    }
    setActionLoading('drain')
    setActionError(null)
    try {
      await nodesAPI.drainNode(nodeName)
      refetch()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to drain node')
    } finally {
      setActionLoading(null)
    }
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">No Cluster Selected</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'status', label: 'Status' },
    { key: 'role', label: 'Role' },
    { key: 'version', label: 'Version' },
    { key: 'age', label: 'Age' },
    { key: 'actions', label: 'Actions' },
  ]

  const getStatusColor = (status) => {
    if (status?.includes('Ready')) return 'text-green-400'
    if (status?.includes('NotReady')) return 'text-red-400'
    return 'text-slate-400'
  }

  const isCordoned = (node) => node.status?.includes('SchedulingDisabled')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Nodes</h1>
        <p className="text-slate-400 mt-2">
          Cluster: <span className="font-semibold text-cyan-400">{activeCluster}</span>
        </p>
      </div>

      {actionError && (
        <div className="glass-card p-4 border-red-500/30">
          <p className="text-red-400 font-medium">Error</p>
          <p className="text-red-300 text-sm mt-1">{actionError}</p>
        </div>
      )}

      {loading && (
        <div className="glass-card p-8 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
          <p className="mt-2 text-slate-400">Loading nodes...</p>
        </div>
      )}

      {error && (
        <div className="glass-card p-4 border-red-500/30">
          <p className="text-red-400 font-medium">Error loading nodes</p>
          <p className="text-red-300 text-sm mt-1">{error}</p>
        </div>
      )}

      {nodes && (
        <div className="glass-card">
          <div className="border-b border-slate-700/50 px-6 py-4">
            <h2 className="text-lg font-semibold text-white">Nodes</h2>
            <p className="text-sm text-slate-400 mt-1">{nodes.length} nodes</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700/50 bg-slate-800/30">
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider"
                    >
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nodes.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length} className="px-6 py-8 text-center text-slate-500">
                      No nodes available in this cluster
                    </td>
                  </tr>
                ) : (
                  nodes.map((node, idx) => (
                    <tr
                      key={idx}
                      className="border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors"
                    >
                      <td className="px-6 py-4">
                        <button
                          onClick={() => handleNodeClick(node)}
                          className="text-sm font-medium text-cyan-400 hover:text-cyan-300"
                        >
                          {node.name}
                        </button>
                      </td>
                      <td className={`px-6 py-4 text-sm ${getStatusColor(node.status)}`}>{node.status}</td>
                      <td className="px-6 py-4 text-sm text-white">{node.role}</td>
                      <td className="px-6 py-4 text-sm text-white">{node.version || '-'}</td>
                      <td className="px-6 py-4 text-sm text-white">{node.age || '-'}</td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2">
                          {isCordoned(node) ? (
                            <button
                              onClick={() => handleUncordon(node.name)}
                              disabled={actionLoading === 'uncordon'}
                              className="px-2 py-1 text-xs bg-yellow-600 text-white rounded hover:bg-yellow-500 disabled:opacity-50"
                            >
                              {actionLoading === 'uncordon' ? 'Uncordon...' : 'Uncordon'}
                            </button>
                          ) : (
                            <button
                              onClick={() => handleCordon(node.name)}
                              disabled={actionLoading === 'cordon'}
                              className="px-2 py-1 text-xs bg-orange-600 text-white rounded hover:bg-orange-500 disabled:opacity-50"
                            >
                              {actionLoading === 'cordon' ? 'Cordon...' : 'Cordon'}
                            </button>
                          )}
                          <button
                            onClick={() => handleDrain(node.name)}
                            disabled={actionLoading === 'drain'}
                            className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-500 disabled:opacity-50"
                          >
                            {actionLoading === 'drain' ? 'Drain...' : 'Drain'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <DetailOverlay
        isOpen={showDetail}
        title={selectedNode?.name}
        data={nodeDetail}
        loading={detailLoading}
        resourceType="nodes"
        onClose={() => setShowDetail(false)}
      />
    </div>
  )
}