/**
 * Resource History Page
 * Timeline view of resource changes with diff and restore capabilities
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useAppContext } from '../context/AppContext'
import { historyAPI } from '../api'
import {
  ClockIcon,
  ArrowPathIcon,
  ArrowUturnLeftIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  FunnelIcon,
  ShieldCheckIcon,
  PencilIcon,
  TrashIcon,
  PhotoIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'

const OPERATION_CONFIG = {
  apply: { label: 'Applied', color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30', icon: PencilIcon },
  delete: { label: 'Deleted', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', icon: TrashIcon },
  scale: { label: 'Scaled', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/30', icon: ArrowsRightLeftIcon },
  'update-image': { label: 'Image Updated', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', icon: PhotoIcon },
  restore: { label: 'Restored', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', icon: ArrowUturnLeftIcon },
}

function DiffViewer({ diffLines }) {
  if (!diffLines || diffLines.length === 0) {
    return <p className="text-slate-500 text-sm">No differences found or identical snapshots.</p>
  }

  return (
    <pre className="bg-slate-900 text-xs font-mono p-4 rounded-lg overflow-auto max-h-96 border border-slate-700">
      {diffLines.map((line, i) => {
        let className = 'text-slate-400'
        if (line.startsWith('+') && !line.startsWith('+++')) className = 'text-green-400'
        else if (line.startsWith('-') && !line.startsWith('---')) className = 'text-red-400'
        else if (line.startsWith('@@')) className = 'text-cyan-400'
        else if (line.startsWith('---') || line.startsWith('+++')) className = 'text-yellow-400 font-bold'
        return <div key={i} className={className}>{line}</div>
      })}
    </pre>
  )
}

function YamlViewer({ yaml, title }) {
  if (!yaml) return <p className="text-slate-500 text-sm">No snapshot available.</p>

  return (
    <div>
      {title && <h5 className="text-xs font-medium text-slate-400 mb-2">{title}</h5>}
      <pre className="bg-slate-900 text-slate-100 text-xs font-mono p-4 rounded-lg overflow-auto max-h-96 border border-slate-700 whitespace-pre-wrap">
        {yaml}
      </pre>
    </div>
  )
}

function HistoryEntry({ entry, onDiff, onRestore, onCompare, selectedForCompare, onToggleCompare }) {
  const [expanded, setExpanded] = useState(false)
  const [yamlData, setYamlData] = useState(null)
  const [loadingYaml, setLoadingYaml] = useState(false)
  const [diffData, setDiffData] = useState(null)
  const [loadingDiff, setLoadingDiff] = useState(false)
  const [restoring, setRestoring] = useState(false)

  const config = OPERATION_CONFIG[entry.operation] || OPERATION_CONFIG.apply
  const OpIcon = config.icon

  const loadYaml = async () => {
    if (yamlData || loadingYaml) return
    setLoadingYaml(true)
    try {
      const res = await historyAPI.getEntry(entry.id)
      setYamlData(res.data)
    } catch (err) {
      console.error('Failed to load YAML:', err)
    } finally {
      setLoadingYaml(false)
    }
  }

  const loadDiff = async () => {
    if (diffData || loadingDiff) return
    setLoadingDiff(true)
    try {
      const res = await historyAPI.getDiff(entry.id)
      setDiffData(res.data)
    } catch (err) {
      console.error('Failed to load diff:', err)
    } finally {
      setLoadingDiff(false)
    }
  }

  const handleExpand = () => {
    setExpanded(!expanded)
    if (!expanded) {
      loadYaml()
      loadDiff()
    }
  }

  const handleRestore = async () => {
    if (!confirm(`Restore ${entry.resource_type}/${entry.resource_name} to this snapshot?`)) return
    setRestoring(true)
    try {
      await onRestore(entry.id)
    } finally {
      setRestoring(false)
    }
  }

  const formatTime = (ts) => {
    if (!ts) return 'N/A'
    const d = new Date(ts)
    return d.toLocaleString()
  }

  const timeAgo = (ts) => {
    if (!ts) return ''
    const now = new Date()
    const then = new Date(ts)
    const diffMs = now - then
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  return (
    <div className={`border rounded-lg ${config.border} ${config.bg} overflow-hidden`}>
      <div className="flex items-center">
        <button
          onClick={handleExpand}
          className="flex-1 flex items-start gap-3 p-4 text-left hover:bg-white/5 transition-colors"
        >
          <OpIcon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.color}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.color} border ${config.border}`}>
                {config.label}
              </span>
              <span className="text-xs text-slate-500">{entry.resource_type}</span>
              {entry.user && <span className="text-xs text-slate-500">by {entry.user}</span>}
            </div>
            <h4 className="text-sm font-medium text-white mt-1 font-mono">{entry.resource_name}</h4>
            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
              <span>{formatTime(entry.timestamp)}</span>
              <span className="text-slate-600">({timeAgo(entry.timestamp)})</span>
              {entry.namespace && <span>ns: {entry.namespace}</span>}
            </div>
          </div>
          {expanded ? (
            <ChevronDownIcon className="h-5 w-5 text-slate-500 flex-shrink-0" />
          ) : (
            <ChevronRightIcon className="h-5 w-5 text-slate-500 flex-shrink-0" />
          )}
        </button>

        <div className="flex items-center gap-1 pr-3">
          <button
            onClick={() => onToggleCompare(entry.id)}
            className={`p-1.5 rounded transition-colors ${
              selectedForCompare === entry.id
                ? 'bg-cyan-500/20 text-cyan-400'
                : 'text-slate-500 hover:text-white hover:bg-slate-700'
            }`}
            title="Select for comparison"
          >
            <ArrowsRightLeftIcon className="h-4 w-4" />
          </button>
          {entry.operation !== 'delete' && (
            <button
              onClick={handleRestore}
              disabled={restoring}
              className="p-1.5 rounded text-slate-500 hover:text-green-400 hover:bg-green-500/10 transition-colors disabled:opacity-50"
              title="Restore this snapshot"
            >
              {restoring ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-green-400 border-t-transparent" />
              ) : (
                <ArrowUturnLeftIcon className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-700/50 pt-3">
          {/* Diff view */}
          {diffData && diffData.diff_lines && diffData.diff_lines.length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-slate-300 mb-2 flex items-center gap-1">
                <CodeBracketIcon className="h-3.5 w-3.5" />
                Change Diff
              </h5>
              <DiffViewer diffLines={diffData.diff_lines} />
            </div>
          )}
          {loadingDiff && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <div className="animate-spin rounded-full h-3 w-3 border border-slate-500 border-t-cyan-500" />
              Loading diff...
            </div>
          )}

          {/* YAML snapshots */}
          {yamlData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {yamlData.yaml_before && (
                <YamlViewer yaml={yamlData.yaml_before} title="Before" />
              )}
              {yamlData.yaml_after && (
                <YamlViewer yaml={yamlData.yaml_after} title="After" />
              )}
              {!yamlData.yaml_before && !yamlData.yaml_after && (
                <p className="text-slate-500 text-sm">No YAML snapshots available.</p>
              )}
            </div>
          )}
          {loadingYaml && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <div className="animate-spin rounded-full h-3 w-3 border border-slate-500 border-t-cyan-500" />
              Loading snapshots...
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function History() {
  const { activeCluster } = useAppContext()
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filterType, setFilterType] = useState('')
  const [filterOperation, setFilterOperation] = useState('')
  const [resourceTypes, setResourceTypes] = useState([])
  const [selectedForCompare, setSelectedForCompare] = useState(null)
  const [compareResult, setCompareResult] = useState(null)
  const [loadingCompare, setLoadingCompare] = useState(false)

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (filterType) params.resource_type = filterType
      if (filterOperation) params.operation = filterOperation
      params.limit = 100

      const res = await historyAPI.list(params)
      setEntries(res.data.entries || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }, [filterType, filterOperation])

  const fetchTypes = useCallback(async () => {
    try {
      const res = await historyAPI.getTypes()
      setResourceTypes(res.data.types || [])
    } catch (err) {
      console.error('Failed to load types:', err)
    }
  }, [])

  useEffect(() => {
    if (activeCluster) {
      fetchHistory()
      fetchTypes()
    }
  }, [activeCluster, fetchHistory, fetchTypes])

  const handleRestore = async (entryId) => {
    try {
      await historyAPI.restore(entryId)
      fetchHistory()
    } catch (err) {
      alert('Restore failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleToggleCompare = (entryId) => {
    if (selectedForCompare === entryId) {
      setSelectedForCompare(null)
      setCompareResult(null)
      return
    }

    if (selectedForCompare && selectedForCompare !== entryId) {
      // Compare the two
      loadCompare(selectedForCompare, entryId)
      setSelectedForCompare(null)
    } else {
      setSelectedForCompare(entryId)
    }
  }

  const loadCompare = async (id1, id2) => {
    setLoadingCompare(true)
    try {
      const res = await historyAPI.getDiff(id1, { compare_with: id2 })
      setCompareResult(res.data)
    } catch (err) {
      alert('Comparison failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoadingCompare(false)
    }
  }

  // Group entries by date
  const groupedByDate = {}
  for (const entry of entries) {
    const date = entry.timestamp ? new Date(entry.timestamp).toLocaleDateString() : 'Unknown'
    if (!groupedByDate[date]) groupedByDate[date] = []
    groupedByDate[date].push(entry)
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Resource History</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Resource History</h1>
          <p className="text-slate-400 mt-2">
            Track resource changes over time, compare versions, and restore previous states
          </p>
        </div>
        <button
          onClick={fetchHistory}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all font-medium"
        >
          {loading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
          ) : (
            <ArrowPathIcon className="h-5 w-5" />
          )}
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-4 w-4 text-slate-500" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
          >
            <option value="">All Resource Types</option>
            {resourceTypes.map(t => (
              <option key={t.resource_type} value={t.resource_type}>
                {t.resource_type} ({t.count})
              </option>
            ))}
          </select>
        </div>
        <select
          value={filterOperation}
          onChange={(e) => setFilterOperation(e.target.value)}
          className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
        >
          <option value="">All Operations</option>
          {Object.entries(OPERATION_CONFIG).map(([key, config]) => (
            <option key={key} value={key}>{config.label}</option>
          ))}
        </select>
        {selectedForCompare && (
          <span className="text-xs text-cyan-400 bg-cyan-500/10 px-3 py-1.5 rounded-lg border border-cyan-500/30">
            Select another entry to compare
          </span>
        )}
      </div>

      {/* Compare Result */}
      {compareResult && (
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <ArrowsRightLeftIcon className="h-4 w-4 text-cyan-400" />
              Comparison: {compareResult.resource_type}/{compareResult.resource_name}
            </h3>
            <button
              onClick={() => setCompareResult(null)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          {loadingCompare ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-400 border-t-transparent" />
              Generating comparison...
            </div>
          ) : (
            <DiffViewer diffLines={compareResult.diff_lines} />
          )}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* History Timeline */}
      {entries.length === 0 && !loading && !error && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <ClockIcon className="h-16 w-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-300">No history yet</h3>
            <p className="text-slate-500 text-sm mt-1">Resource changes will appear here as you apply, scale, or delete resources</p>
          </div>
        </div>
      )}

      {Object.entries(groupedByDate).map(([date, dateEntries]) => (
        <div key={date}>
          <div className="flex items-center gap-3 mb-3">
            <div className="h-px flex-1 bg-slate-700/50" />
            <span className="text-xs font-medium text-slate-500 bg-slate-800/50 px-3 py-1 rounded-full">{date}</span>
            <div className="h-px flex-1 bg-slate-700/50" />
          </div>
          <div className="space-y-2">
            {dateEntries.map(entry => (
              <HistoryEntry
                key={entry.id}
                entry={entry}
                onRestore={handleRestore}
                onToggleCompare={handleToggleCompare}
                selectedForCompare={selectedForCompare}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
