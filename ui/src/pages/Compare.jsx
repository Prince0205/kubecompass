/**
 * Multi-Cluster Compare Page
 * Side-by-side comparison of resources across Kubernetes clusters
 * Detects configuration drift with diff highlighting
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useAppContext } from '../context/AppContext'
import { compareAPI } from '../api'
import {
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  MinusCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'

const STATUS_CONFIG = {
  identical: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', icon: CheckCircleIcon, label: 'Identical' },
  drifted: { color: '#eab308', bg: 'rgba(234,179,8,0.1)', icon: ExclamationTriangleIcon, label: 'Drifted' },
  only_in_a: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', icon: MinusCircleIcon, label: 'Only in A' },
  only_in_b: { color: '#a855f7', bg: 'rgba(168,85,247,0.1)', icon: MinusCircleIcon, label: 'Only in B' },
}

function DiffLine({ line }) {
  let bg = 'transparent'
  let textColor = '#94a3b8'
  let prefix = ' '

  if (line.startsWith('+') && !line.startsWith('+++')) {
    bg = 'rgba(34,197,94,0.12)'
    textColor = '#4ade80'
    prefix = '+'
  } else if (line.startsWith('-') && !line.startsWith('---')) {
    bg = 'rgba(239,68,68,0.12)'
    textColor = '#f87171'
    prefix = '-'
  } else if (line.startsWith('@@')) {
    bg = 'rgba(59,130,246,0.08)'
    textColor = '#60a5fa'
    prefix = ''
  }

  return (
    <div
      style={{
        backgroundColor: bg,
        color: textColor,
        padding: '1px 8px',
        fontFamily: 'monospace',
        fontSize: 12,
        whiteSpace: 'pre',
        lineHeight: '18px',
      }}
    >
      {prefix && <span style={{ opacity: 0.5, marginRight: 4 }}>{prefix}</span>}
      {line}
    </div>
  )
}

function ResourceComparison({ comp, clusterAName, clusterBName }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CONFIG[comp.status]
  const StatusIcon = cfg.icon

  return (
    <div
      className="border rounded-lg overflow-hidden mb-3"
      style={{ borderColor: cfg.color + '40' }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-slate-800/50 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDownIcon className="h-4 w-4 text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronRightIcon className="h-4 w-4 text-slate-400 flex-shrink-0" />
        )}
        <StatusIcon className="h-5 w-5 flex-shrink-0" style={{ color: cfg.color }} />
        <span className="text-sm font-medium text-white flex-1 truncate">{comp.resource_key}</span>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{ color: cfg.color, backgroundColor: cfg.bg }}
        >
          {cfg.label}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-slate-700">
          {/* Side-by-side YAML */}
          <div className="grid grid-cols-2">
            <div className="border-r border-slate-700">
              <div className="px-3 py-1.5 bg-slate-800/50 text-xs font-semibold text-blue-400 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                {clusterAName}
                {!comp.in_cluster_a && <span className="text-slate-500 ml-1">(not present)</span>}
              </div>
              <pre className="p-3 text-xs text-slate-300 overflow-auto max-h-[300px] bg-slate-900/50" style={{ margin: 0 }}>
                {comp.yaml_a || '(resource not found)'}
              </pre>
            </div>
            <div>
              <div className="px-3 py-1.5 bg-slate-800/50 text-xs font-semibold text-purple-400 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-purple-500" />
                {clusterBName}
                {!comp.in_cluster_b && <span className="text-slate-500 ml-1">(not present)</span>}
              </div>
              <pre className="p-3 text-xs text-slate-300 overflow-auto max-h-[300px] bg-slate-900/50" style={{ margin: 0 }}>
                {comp.yaml_b || '(resource not found)'}
              </pre>
            </div>
          </div>

          {/* Diff view */}
          {comp.diff && comp.diff.length > 0 && (
            <div className="border-t border-slate-700">
              <div className="px-3 py-1.5 bg-slate-800/50 text-xs font-semibold text-slate-400">
                Diff
              </div>
              <div className="max-h-[200px] overflow-auto">
                {comp.diff.map((line, i) => (
                  <DiffLine key={i} line={line.replace(/\n$/, '')} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Compare() {
  const { auth } = useAppContext()
  const [clusters, setClusters] = useState([])
  const [resourceTypes, setResourceTypes] = useState([])
  const [clusterA, setClusterA] = useState('')
  const [clusterB, setClusterB] = useState('')
  const [resourceType, setResourceType] = useState('deployments')
  const [namespace, setNamespace] = useState('default')
  const [namespacesA, setNamespacesA] = useState([])
  const [namespacesB, setNamespacesB] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingClusters, setLoadingClusters] = useState(true)
  const [error, setError] = useState(null)
  const [filterStatus, setFilterStatus] = useState('all')

  useEffect(() => {
    const loadInitial = async () => {
      try {
        const [clustersRes, typesRes] = await Promise.all([
          compareAPI.getClusters(),
          compareAPI.getResourceTypes(),
        ])
        const clusterList = clustersRes.data || []
        setClusters(clusterList)
        setResourceTypes(typesRes.data || [])
        if (clusterList.length >= 2) {
          setClusterA(clusterList[0].id)
          setClusterB(clusterList[1].id)
        }
      } catch (err) {
        setError('Failed to load clusters')
      } finally {
        setLoadingClusters(false)
      }
    }
    if (auth) loadInitial()
  }, [auth])

  // Load namespaces when clusters change
  useEffect(() => {
    if (clusterA) {
      compareAPI.getNamespaces(clusterA)
        .then(r => setNamespacesA(r.data || []))
        .catch(() => setNamespacesA([]))
    }
  }, [clusterA])

  useEffect(() => {
    if (clusterB) {
      compareAPI.getNamespaces(clusterB)
        .then(r => setNamespacesB(r.data || []))
        .catch(() => setNamespacesB([]))
    }
  }, [clusterB])

  const handleCompare = useCallback(async () => {
    if (!clusterA || !clusterB || clusterA === clusterB) {
      setError('Select two different clusters')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await compareAPI.getResources(clusterA, clusterB, resourceType, namespace)
      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Comparison failed')
    } finally {
      setLoading(false)
    }
  }, [clusterA, clusterB, resourceType, namespace])

  const clusterAName = clusters.find(c => c.id === clusterA)?.name || 'Cluster A'
  const clusterBName = clusters.find(c => c.id === clusterB)?.name || 'Cluster B'

  const filteredComparisons = result?.comparisons?.filter(c => {
    if (filterStatus === 'all') return true
    return c.status === filterStatus
  }) || []

  if (!auth) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Multi-Cluster Compare</h2>
        <p className="text-slate-400 mt-2">Please log in to use the comparison feature.</p>
      </div>
    )
  }

  if (loadingClusters) {
    return (
      <div className="glass-card p-6 flex items-center gap-3">
        <div className="animate-spin rounded-full h-5 w-5 border-2 border-cyan-500 border-t-transparent" />
        <span className="text-slate-400">Loading clusters...</span>
      </div>
    )
  }

  if (clusters.length < 2) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Multi-Cluster Compare</h2>
        <p className="text-slate-400 mt-2">
          At least 2 clusters are required for comparison. Currently registered: {clusters.length}.
        </p>
        <p className="text-slate-500 text-sm mt-1">
          Upload additional cluster kubeconfigs to enable comparison.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Multi-Cluster Compare</h1>
        <p className="text-slate-400 mt-1">Side-by-side comparison of resources across clusters to detect configuration drift</p>
      </div>

      {/* Selection Controls */}
      <div className="glass-card p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Cluster A */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Cluster A</label>
            <select
              value={clusterA}
              onChange={e => setClusterA(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {clusters.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Cluster B */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Cluster B</label>
            <select
              value={clusterB}
              onChange={e => setClusterB(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              {clusters.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Resource Type */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Resource Type</label>
            <select
              value={resourceType}
              onChange={e => setResourceType(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
            >
              {resourceTypes.map(rt => (
                <option key={rt.key} value={rt.key}>{rt.kind}</option>
              ))}
            </select>
          </div>

          {/* Namespace */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">Namespace</label>
            <input
              type="text"
              value={namespace}
              onChange={e => setNamespace(e.target.value)}
              placeholder="default"
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleCompare}
            disabled={loading || clusterA === clusterB}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all font-medium"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
            ) : (
              <ArrowPathIcon className="h-5 w-5" />
            )}
            Compare
          </button>
          {clusterA === clusterB && (
            <span className="text-xs text-amber-400">Select two different clusters</span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary Bar */}
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white">
                Comparing <span className="text-blue-400">{clusterAName}</span> vs{' '}
                <span className="text-purple-400">{clusterBName}</span>
                <span className="text-slate-500 ml-2">
                  {resourceType} in {result.namespace}
                </span>
              </h3>
            </div>
            <div className="flex gap-3 flex-wrap">
              {Object.entries(result.summary).map(([key, count]) => {
                if (key === 'total') return null
                const cfg = STATUS_CONFIG[key]
                if (!cfg) return null
                return (
                  <button
                    key={key}
                    onClick={() => setFilterStatus(filterStatus === key ? 'all' : key)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                      filterStatus === key ? 'ring-2' : ''
                    }`}
                    style={{
                      borderColor: cfg.color + '60',
                      color: cfg.color,
                      backgroundColor: cfg.bg,
                      ...(filterStatus === key ? { ringColor: cfg.color } : {}),
                    }}
                  >
                    <cfg.icon className="h-4 w-4" />
                    {cfg.label}: {count}
                  </button>
                )
              })}
              <span className="text-xs text-slate-500 flex items-center ml-auto">
                Total: {result.summary.total} resources
              </span>
            </div>
          </div>

          {/* Resource List */}
          <div>
            {filteredComparisons.length === 0 ? (
              <div className="glass-card p-8 text-center">
                <CheckCircleIcon className="h-12 w-12 text-green-500 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-white">
                  {filterStatus === 'all' ? 'No resources found' : `No ${filterStatus} resources`}
                </h3>
                <p className="text-slate-400 text-sm mt-1">
                  {filterStatus === 'all'
                    ? 'No resources found in the selected namespace'
                    : 'All matching resources have the selected status'}
                </p>
              </div>
            ) : (
              filteredComparisons.map((comp) => (
                <ResourceComparison
                  key={comp.resource_key}
                  comp={comp}
                  clusterAName={clusterAName}
                  clusterBName={clusterBName}
                />
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}
