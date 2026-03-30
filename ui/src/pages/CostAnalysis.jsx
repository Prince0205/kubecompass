/**
 * Cost Analysis Page
 * Resource cost estimation based on CPU/memory requests with right-sizing recommendations
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useAppContext } from '../context/AppContext'
import { costAPI } from '../api'
import {
  CurrencyDollarIcon,
  ChartPieIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowDownIcon,
  CubeIcon,
} from '@heroicons/react/24/outline'
import {
  PieChart, Pie, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const COLORS = ['#06B6D4', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#3B82F6', '#14B8A6', '#F97316', '#6366F1']

function formatCurrency(val) {
  if (val === undefined || val === null) return '$0.00'
  return `$${Number(val).toFixed(2)}`
}

function CustomTooltip({ active, payload }) {
  if (active && payload && payload.length) {
    const d = payload[0].payload
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 shadow-lg">
        <p className="text-white text-sm font-medium">{d.namespace || d.name || d.label}</p>
        <p className="text-cyan-400 font-semibold">{formatCurrency(d.total_cost_month || d.value)}</p>
        {d.pod_count !== undefined && <p className="text-slate-400 text-xs">{d.pod_count} pods</p>}
      </div>
    )
  }
  return null
}

function CostCard({ title, value, subtitle, icon: Icon, color = 'cyan' }) {
  const colorClasses = {
    cyan: 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30 text-cyan-400',
    green: 'from-green-500/20 to-green-600/10 border-green-500/30 text-green-400',
    purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-400',
    orange: 'from-orange-500/20 to-orange-600/10 border-orange-500/30 text-orange-400',
  }

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} border rounded-xl p-5`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-400">{title}</p>
          <p className={`text-2xl font-bold mt-1 ${colorClasses[color].split(' ')[2]}`}>{value}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        <Icon className="h-10 w-10 text-slate-600" />
      </div>
    </div>
  )
}

export default function CostAnalysis() {
  const { activeCluster, activeNamespace } = useAppContext()
  const [costData, setCostData] = useState(null)
  const [rightsizingData, setRightsizingData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [costRes, rightRes] = await Promise.all([
        costAPI.analyze(),
        costAPI.rightsize(),
      ])
      setCostData(costRes.data)
      setRightsizingData(rightRes.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load cost data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeCluster) fetchData()
  }, [activeCluster, fetchData])

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Cost Analysis</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  // Namespace pie chart data
  const nsPieData = (costData?.namespace_breakdown || []).map(ns => ({
    name: ns.namespace,
    value: ns.total_cost_month,
    label: ns.namespace,
    total_cost_month: ns.total_cost_month,
    pod_count: ns.pod_count,
  })).filter(d => d.value > 0)

  // Workload bar chart data (top 15)
  const workloadBarData = (costData?.workload_breakdown || []).slice(0, 15).map(w => ({
    name: w.name.length > 20 ? w.name.slice(0, 18) + '...' : w.name,
    CPU: w.cpu_cost_month,
    Memory: w.memory_cost_month,
    total: w.total_cost_month,
  }))

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'namespaces', label: 'Namespaces' },
    { key: 'workloads', label: 'Workloads' },
    { key: 'rightsizing', label: 'Right-Sizing' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Cost Analysis</h1>
          <p className="text-slate-400 mt-2">Resource cost estimation and optimization recommendations</p>
        </div>
        <button
          onClick={fetchData}
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

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">{error}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/50 rounded-lg p-1">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-cyan-500/20 text-cyan-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && !costData && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 mx-auto mb-4"></div>
            <p className="text-slate-400">Analyzing costs...</p>
          </div>
        </div>
      )}

      {costData && (
        <>
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <CostCard
                  title="Total Monthly Cost"
                  value={formatCurrency(costData.total_monthly_cost)}
                  subtitle={`${costData.pod_count} pods across ${costData.node_count} nodes`}
                  icon={CurrencyDollarIcon}
                  color="cyan"
                />
                <CostCard
                  title="CPU Cost"
                  value={formatCurrency(costData.cpu_cost_month)}
                  subtitle="Per month based on requests"
                  icon={CubeIcon}
                  color="purple"
                />
                <CostCard
                  title="Memory Cost"
                  value={formatCurrency(costData.memory_cost_month)}
                  subtitle="Per month based on requests"
                  icon={ChartPieIcon}
                  color="green"
                />
                <CostCard
                  title="Storage Cost"
                  value={formatCurrency(costData.storage_cost_month)}
                  subtitle="Per month PVC storage"
                  icon={CubeIcon}
                  color="orange"
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Namespace Pie Chart */}
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold text-white mb-4">Cost by Namespace</h3>
                  {nsPieData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={nsPieData}
                          cx="50%"
                          cy="50%"
                          outerRadius={100}
                          dataKey="value"
                          label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                          labelLine={{ stroke: '#64748B' }}
                        >
                          {nsPieData.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-slate-500 text-center py-10">No cost data available</p>
                  )}
                </div>

                {/* Top Workloads Bar Chart */}
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold text-white mb-4">Top Workloads by Cost</h3>
                  {workloadBarData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={workloadBarData} layout="vertical" margin={{ left: 80 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis type="number" tick={{ fill: '#94A3B8', fontSize: 11 }} tickFormatter={v => `$${v}`} />
                        <YAxis type="category" dataKey="name" tick={{ fill: '#94A3B8', fontSize: 11 }} width={80} />
                        <Tooltip
                          formatter={(value) => formatCurrency(value)}
                          contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#F1F5F9' }}
                        />
                        <Legend />
                        <Bar dataKey="CPU" stackId="a" fill="#8B5CF6" />
                        <Bar dataKey="Memory" stackId="a" fill="#06B6D4" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-slate-500 text-center py-10">No workload data</p>
                  )}
                </div>
              </div>

              {/* Pricing Info */}
              <div className="glass-card p-5">
                <h3 className="text-sm font-semibold text-white mb-3">Pricing Assumptions</h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-slate-400">CPU</p>
                    <p className="text-white font-medium">${costData.pricing.cpu_per_core_hour}/core/hour</p>
                    <p className="text-slate-500 text-xs">~${(costData.pricing.cpu_per_core_hour * 730).toFixed(0)}/core/month</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Memory</p>
                    <p className="text-white font-medium">${costData.pricing.memory_per_gb_hour}/GB/hour</p>
                    <p className="text-slate-500 text-xs">~${(costData.pricing.memory_per_gb_hour * 730).toFixed(2)}/GB/month</p>
                  </div>
                  <div>
                    <p className="text-slate-400">Storage</p>
                    <p className="text-white font-medium">${costData.pricing.storage_per_gb_month}/GB/month</p>
                    <p className="text-slate-500 text-xs">Persistent volume storage</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Namespaces Tab */}
          {activeTab === 'namespaces' && (
            <div className="space-y-4">
              <div className="glass-card overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/50">
                    <tr>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Namespace</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Pods</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">CPU Cores</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Memory (GB)</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">CPU Cost</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Memory Cost</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Total/Month</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(costData.namespace_breakdown || []).map(ns => (
                      <tr key={ns.namespace} className="border-t border-slate-700/50 hover:bg-slate-800/30">
                        <td className="px-4 py-3 text-white font-medium">{ns.namespace}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{ns.pod_count}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{ns.total_cpu_cores}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{ns.total_memory_gb}</td>
                        <td className="px-4 py-3 text-right text-purple-400">{formatCurrency(ns.cpu_cost_month)}</td>
                        <td className="px-4 py-3 text-right text-cyan-400">{formatCurrency(ns.memory_cost_month)}</td>
                        <td className="px-4 py-3 text-right text-white font-semibold">{formatCurrency(ns.total_cost_month)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Workloads Tab */}
          {activeTab === 'workloads' && (
            <div className="space-y-4">
              <div className="glass-card overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/50">
                    <tr>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Workload</th>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Kind</th>
                      <th className="text-left px-4 py-3 text-slate-400 font-medium">Namespace</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Pods</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">CPU</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Memory</th>
                      <th className="text-right px-4 py-3 text-slate-400 font-medium">Total/Month</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(costData.workload_breakdown || []).map((w, i) => (
                      <tr key={i} className="border-t border-slate-700/50 hover:bg-slate-800/30">
                        <td className="px-4 py-3 text-white font-medium">{w.name}</td>
                        <td className="px-4 py-3 text-slate-400">{w.kind}</td>
                        <td className="px-4 py-3 text-slate-300">{w.namespace}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{w.pod_count}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatCurrency(w.cpu_cost_month)}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatCurrency(w.memory_cost_month)}</td>
                        <td className="px-4 py-3 text-right text-white font-semibold">{formatCurrency(w.total_cost_month)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Right-Sizing Tab */}
          {activeTab === 'rightsizing' && rightsizingData && (
            <div className="space-y-4">
              {!rightsizingData.has_metrics && (
                <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-400 text-sm flex items-center gap-2">
                  <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0" />
                  Metrics Server not available. Showing recommendations based on request patterns only. Install Metrics Server for usage-based recommendations.
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="glass-card p-5 flex items-center gap-4">
                  <ArrowDownIcon className="h-10 w-10 text-green-400" />
                  <div>
                    <p className="text-sm text-slate-400">Potential Monthly Savings</p>
                    <p className="text-2xl font-bold text-green-400">{formatCurrency(rightsizingData.potential_savings_month)}</p>
                  </div>
                </div>
                <div className="glass-card p-5 flex items-center gap-4">
                  <ExclamationTriangleIcon className="h-10 w-10 text-orange-400" />
                  <div>
                    <p className="text-sm text-slate-400">Workloads Needing Attention</p>
                    <p className="text-2xl font-bold text-orange-400">{rightsizingData.total_recommendations}</p>
                  </div>
                </div>
              </div>

              {rightsizingData.recommendations.length === 0 ? (
                <div className="flex items-center justify-center py-16">
                  <div className="text-center">
                    <CheckCircleIcon className="h-12 w-12 text-green-500 mx-auto mb-3" />
                    <h3 className="text-lg font-medium text-green-400">All workloads look good!</h3>
                    <p className="text-slate-500 text-sm mt-1">No right-sizing recommendations at this time</p>
                  </div>
                </div>
              ) : (
                <div className="glass-card overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-800/50">
                      <tr>
                        <th className="text-left px-4 py-3 text-slate-400 font-medium">Workload</th>
                        <th className="text-left px-4 py-3 text-slate-400 font-medium">Status</th>
                        <th className="text-right px-4 py-3 text-slate-400 font-medium">CPU Util</th>
                        <th className="text-right px-4 py-3 text-slate-400 font-medium">Mem Util</th>
                        <th className="text-right px-4 py-3 text-slate-400 font-medium">Current</th>
                        <th className="text-right px-4 py-3 text-slate-400 font-medium">Recommended</th>
                        <th className="text-right px-4 py-3 text-slate-400 font-medium">Savings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rightsizingData.recommendations.map((r, i) => (
                        <tr key={i} className="border-t border-slate-700/50 hover:bg-slate-800/30">
                          <td className="px-4 py-3">
                            <p className="text-white font-medium">{r.controller_name}</p>
                            <p className="text-xs text-slate-500">{r.namespace}/{r.controller_kind}</p>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                              r.status === 'over-provisioned'
                                ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30'
                                : 'bg-red-500/10 text-red-400 border border-red-500/30'
                            }`}>
                              {r.status === 'over-provisioned' ? 'Over-provisioned' : 'Under-provisioned'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">{r.cpu_utilization}%</td>
                          <td className="px-4 py-3 text-right">{r.memory_utilization}%</td>
                          <td className="px-4 py-3 text-right text-slate-300">{formatCurrency(r.current_cost_month)}</td>
                          <td className="px-4 py-3 text-right text-cyan-400">{formatCurrency(r.recommended_cost_month)}</td>
                          <td className="px-4 py-3 text-right text-green-400 font-semibold">{formatCurrency(r.savings_month)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
