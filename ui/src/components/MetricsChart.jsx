/**
 * MetricsChart Component
 * Displays metrics using Recharts
 */

import React from 'react'
import { PieChart, Pie, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#06B6D4', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']

export default function MetricsChart({
  title,
  type = 'bar',
  data = [],
  dataKey = 'value',
  loading = false,
  error = null
}) {
  const titleLower = (title || '').toLowerCase()
  const keyLower = (dataKey || '').toLowerCase()
  const isMemoryChart = keyLower.includes('memory') || titleLower.includes('memory')
  const isCpuChart = keyLower.includes('cpu') || titleLower.includes('cpu')
  
  const formatValue = (val) => {
    if (val === undefined || val === null) return '0'
    const num = parseFloat(val)
    if (isNaN(num)) return String(val)
    
    if (isMemoryChart) {
      const gb = num / (1024 * 1024 * 1024)
      if (gb >= 1) return `${gb.toFixed(2)} GB`
      return `${(num / (1024 * 1024)).toFixed(2)} MB`
    }
    if (isCpuChart) {
      if (num >= 1) return `${num.toFixed(2)} cores`
      return `${(num * 1000).toFixed(0)}m`
    }
    return num
  }
  
  const formatLabel = (val) => {
    return formatValue(val)
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 shadow-lg">
          <p className="text-slate-300 text-sm">{payload[0].name}</p>
          <p className="text-cyan-400 font-semibold">{formatValue(payload[0].value)}</p>
        </div>
      )
    }
    return null
  }

  if (loading) {
    return (
      <div className="glass-card p-6">
        <div className="h-80 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
            <p className="mt-2 text-slate-400">Loading metrics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-card p-4 border-red-500/30">
        <p className="text-red-400 font-medium">{title}</p>
        <p className="text-red-300 text-sm mt-1">{error}</p>
      </div>
    )
  }

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>

      {data.length === 0 ? (
        <div className="h-80 flex items-center justify-center text-slate-500">
          No data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          {type === 'pie' ? (
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${formatValue(value)}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey={dataKey}
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} formatter={formatValue} />
            </PieChart>
          ) : type === 'line' ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94A3B8" tick={{ fill: '#94A3B8' }} />
              <YAxis stroke="#94A3B8" tick={{ fill: '#94A3B8' }} tickFormatter={formatValue} />
              <Tooltip content={<CustomTooltip />} formatter={formatValue} />
              <Legend wrapperStyle={{ color: '#94A3B8' }} />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke="#06B6D4"
                dot={{ fill: '#06B6D4', strokeWidth: 2 }}
                strokeWidth={2}
              />
            </LineChart>
          ) : (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94A3B8" tick={{ fill: '#94A3B8' }} />
              <YAxis stroke="#94A3B8" tick={{ fill: '#94A3B8' }} tickFormatter={formatValue} domain={[0, 'auto']} />
              <Tooltip content={<CustomTooltip />} formatter={formatValue} />
              <Legend wrapperStyle={{ color: '#94A3B8' }} />
              <Bar dataKey={dataKey} fill="#06B6D4" label={formatLabel} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      )}
    </div>
  )
}