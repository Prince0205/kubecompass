/**
 * ResourceList Component
 * Displays resources in a table with sorting and filtering
 */

import React, { useState, useMemo } from 'react'
import { ChevronUpDownIcon } from '@heroicons/react/24/outline'

const getNestedValue = (obj, path) => {
  if (!path || !obj) return undefined
  const keys = path.split('.')
  let value = obj
  for (const key of keys) {
    if (value === undefined || value === null) return undefined
    value = value[key]
  }
  return value
}

export default function ResourceList({
  title,
  items = [],
  columns = [],
  loading = false,
  error = null,
  onRowClick = null,
  resourceType = ''
}) {
  const [sortBy, setSortBy] = useState(null)
  const [sortDir, setSortDir] = useState('asc')
  const [filter, setFilter] = useState('')

  const filtered = useMemo(() => {
    return items.filter(item => {
      if (!filter) return true
      return JSON.stringify(item).toLowerCase().includes(filter.toLowerCase())
    })
  }, [items, filter])

  const sorted = useMemo(() => {
    if (!sortBy) return filtered
    return [...filtered].sort((a, b) => {
      const aVal = getNestedValue(a, sortBy.key)
      const bVal = getNestedValue(b, sortBy.key)

      if (aVal === undefined || aVal === null) return sortDir === 'asc' ? 1 : -1
      if (bVal === undefined || bVal === null) return sortDir === 'asc' ? -1 : 1

      if (typeof aVal === 'string') {
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }

      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
  }, [filtered, sortBy, sortDir])

  const handleSort = (col) => {
    if (sortBy?.key === col.key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortDir('asc')
    }
  }

  if (loading) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
        <p className="mt-2 text-slate-400">Loading {title.toLowerCase()}...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-card p-4 border-red-500/30">
        <p className="text-red-400 font-medium">Error loading {title}</p>
        <p className="text-red-300 text-sm mt-1">{error}</p>
      </div>
    )
  }

  return (
    <div className="glass-card">
      <div className="border-b border-slate-700/50 px-6 py-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <p className="text-sm text-slate-400 mt-1">{sorted.length} items</p>
      </div>

      <div className="border-b border-slate-700/50 px-6 py-3">
        <input
          type="text"
          placeholder="Filter resources..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input-dark w-full text-sm"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700/50 bg-slate-800/30">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col)}
                  className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider cursor-pointer hover:bg-slate-700/30"
                >
                  <div className="flex items-center gap-2">
                    {col.label}
                    {sortBy?.key === col.key && (
                      <ChevronUpDownIcon className="h-4 w-4 text-cyan-500" />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-8 text-center text-slate-500">
                  No {title.toLowerCase()} available in this namespace
                </td>
              </tr>
            ) : (
              sorted.map((item) => (
                <tr
                  key={item.metadata?.uid || item.id || item.name || Math.random()}
                  onClick={() => onRowClick?.(item)}
                  className="border-b border-slate-700/30 hover:bg-slate-700/20 cursor-pointer transition-colors"
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-6 py-4 text-sm text-white">
                      {col.render
                        ? col.render(getNestedValue(item, col.key), item)
                        : getNestedValue(item, col.key) || '-'}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}