/**
 * Topology Graph Page
 * Interactive visualization of Kubernetes resource relationships
 * Uses React Flow with dagre for hierarchical auto-positioning
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import { useAppContext } from '../context/AppContext'
import { topologyAPI } from '../api'
import { ArrowPathIcon, CubeIcon } from '@heroicons/react/24/outline'

const KIND_CONFIG = {
  Deployment: { color: '#3b82f6', label: 'Deployment' },
  ReplicaSet: { color: '#8b5cf6', label: 'ReplicaSet' },
  Pod: { color: '#22c55e', label: 'Pod' },
  StatefulSet: { color: '#f59e0b', label: 'StatefulSet' },
  DaemonSet: { color: '#f97316', label: 'DaemonSet' },
  Job: { color: '#06b6d4', label: 'Job' },
  CronJob: { color: '#14b8a6', label: 'CronJob' },
  Service: { color: '#ec4899', label: 'Service' },
  Ingress: { color: '#a855f7', label: 'Ingress' },
  ConfigMap: { color: '#64748b', label: 'ConfigMap' },
  Secret: { color: '#ef4444', label: 'Secret' },
  PersistentVolumeClaim: { color: '#eab308', label: 'PVC' },
  PersistentVolume: { color: '#84cc16', label: 'PV' },
}

const EDGE_COLORS = {
  owns: '#3b82f6',
  selector: '#ec4899',
  routes: '#a855f7',
  mounts: '#64748b',
  claims: '#eab308',
  bound: '#84cc16',
}

function layoutGraph(backendNodes, backendEdges) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', nodesep: 70, ranksep: 110, marginx: 50, marginy: 50 })

  const W = 170
  const H = 70

  const validIds = new Set(backendNodes.map((n) => n.id))
  for (const n of backendNodes) {
    g.setNode(n.id, { width: W, height: H })
  }
  for (const e of backendEdges) {
    if (validIds.has(e.source) && validIds.has(e.target)) {
      g.setEdge(e.source, e.target)
    }
  }

  dagre.layout(g)

  const nodes = backendNodes.map((n) => {
    const pos = g.node(n.id)
    const cfg = KIND_CONFIG[n.kind] || { color: '#6b7280' }
    return {
      id: n.id,
      data: {
        label: `${n.kind}: ${n.name}`,
        kind: n.kind,
        status: n.status,
        color: cfg.color,
      },
      position: { x: pos ? pos.x - W / 2 : 0, y: pos ? pos.y - H / 2 : 0 },
      style: {
        background: '#1e293b',
        border: `2px solid ${cfg.color}`,
        color: '#f1f5f9',
        borderRadius: 8,
        padding: '6px 10px',
        fontSize: 12,
        fontWeight: 500,
        width: W,
        boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
      },
    }
  })

  const validNodeIds = new Set(nodes.map((n) => n.id))
  const edges = backendEdges
    .filter((e) => validNodeIds.has(e.source) && validNodeIds.has(e.target))
    .map((e, i) => {
      const color = EDGE_COLORS[e.label] || '#6b7280'
      return {
        id: `edge-${i}`,
        source: e.source,
        target: e.target,
        label: e.label,
        animated: e.label === 'owns',
        style: { stroke: color, strokeWidth: 2 },
        labelStyle: { fill: '#e2e8f0', fontSize: 11, fontWeight: 600 },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.95 },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 6,
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 18, height: 18 },
      }
    })

  return { nodes, edges }
}

export default function Topology() {
  const { activeCluster, activeNamespace } = useAppContext()
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [nodes, setNodes] = useState([])
  const [edges, setEdges] = useState([])

  const fetchGraph = useCallback(async () => {
    if (!activeCluster) return
    setLoading(true)
    setError(null)
    try {
      const res = await topologyAPI.getGraph(activeNamespace)
      setGraphData(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load topology')
    } finally {
      setLoading(false)
    }
  }, [activeCluster, activeNamespace])

  useEffect(() => { fetchGraph() }, [fetchGraph])

  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) {
      setNodes([])
      setEdges([])
      return
    }
    const result = layoutGraph(graphData.nodes, graphData.edges)
    console.log('[Topology] Setting', result.nodes.length, 'nodes and', result.edges.length, 'edges')
    setNodes(result.nodes)
    setEdges(result.edges)
  }, [graphData])

  const stats = useMemo(() => {
    if (!graphData) return null
    const counts = {}
    for (const n of graphData.nodes) counts[n.kind] = (counts[n.kind] || 0) + 1
    return counts
  }, [graphData])

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Topology Graph</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4 h-[calc(100vh-140px)] flex flex-col">
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold text-white">Topology Graph</h1>
          <p className="text-slate-400 mt-1">Visual map of resource relationships and dependencies</p>
        </div>
        <div className="flex items-center gap-3">
          {graphData && (
            <span className="text-xs text-slate-500">
              {graphData.total_nodes} nodes, {graphData.total_edges} edges
            </span>
          )}
          <button
            onClick={fetchGraph}
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
      </div>

      {stats && (
        <div className="flex gap-2 flex-wrap flex-shrink-0">
          {Object.entries(stats).map(([kind, count]) => {
            const cfg = KIND_CONFIG[kind] || { color: '#6b7280' }
            return (
              <span key={kind} className="px-2 py-1 rounded text-xs font-medium border"
                style={{ borderColor: cfg.color, color: cfg.color, backgroundColor: `${cfg.color}15` }}>
                {kind}: {count}
              </span>
            )
          })}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex-shrink-0">{error}</div>
      )}

      <div className="flex-1 rounded-xl border border-slate-700 bg-slate-900/50 overflow-hidden relative">
        {loading && !graphData && (
          <div className="absolute inset-0 flex items-center justify-center z-20 bg-slate-900/80">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-cyan-500 border-t-transparent mx-auto mb-3" />
              <p className="text-slate-400 text-sm">Building topology graph...</p>
            </div>
          </div>
        )}

        {!loading && graphData && graphData.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="text-center">
              <CubeIcon className="h-16 w-16 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-300">No resources found</h3>
              <p className="text-slate-500 text-sm mt-1">Deploy some resources to see the topology graph</p>
            </div>
          </div>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          minZoom={0.05}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Controls className="!bg-slate-800 !border-slate-700 !rounded-lg" />
          <Background color="#334155" gap={20} size={1} />
          <MiniMap
            nodeColor={(node) => node.data?.color || '#6b7280'}
            maskColor="rgba(15, 23, 42, 0.8)"
            className="!bg-slate-800 !border-slate-700 !rounded-lg"
          />
        </ReactFlow>

        <div className="absolute bottom-4 left-4 bg-slate-800/90 backdrop-blur-sm border border-slate-700 rounded-lg p-3 z-10">
          <h4 className="text-xs font-semibold text-slate-300 mb-2">Edge Types</h4>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(EDGE_COLORS).map(([key, color]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span className="w-4 h-0.5" style={{ backgroundColor: color }} />
                <span className="text-[10px] text-slate-400">{key}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
