/**
 * Header Component
 * Displays active cluster and namespace selectors with dropdown menus
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppContext } from '../context/AppContext'

export default function Header() {
  const navigate = useNavigate()
  const {
    auth,
    activeCluster,
    activeNamespace,
    clusters,
    namespaces,
    selectCluster,
    selectNamespace,
    loading,
    logout,
  } = useAppContext()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const handleClusterChange = async (clusterId) => {
    await selectCluster(clusterId)
  }

  const handleNamespaceChange = async (namespace) => {
    await selectNamespace(namespace)
  }

  const currentCluster = clusters.find((c) => c.id === activeCluster)
  const clusterName = currentCluster?.name || 'Select Cluster'

  const now = new Date()
  const formattedDate = now.toLocaleDateString('en-US', { 
    weekday: 'long', 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short'
  })

  return (
    <div className="glass-panel border-t-0 border-x-0 rounded-none px-6 py-3">
      <div className="flex items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-9 h-9">
              <circle cx="32" cy="32" r="28" stroke="url(#headerGrad)" strokeWidth="2" fill="none"/>
              <defs>
                <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#06B6D4" />
                  <stop offset="100%" stopColor="#2563EB" />
                </linearGradient>
              </defs>
              <path d="M32 14 L34 26 L32 28 L30 26 Z" fill="#06B6D4"/>
              <path d="M32 50 L30 38 L32 36 L34 38 Z" fill="#2563EB"/>
              <circle cx="32" cy="32" r="5" fill="#0F172A" stroke="#06B6D4" strokeWidth="1"/>
              <text x="32" y="34.5" textAnchor="middle" fill="#06B6D4" fontSize="5" fontWeight="bold">K</text>
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide">KUBERNETES COMPASS</h1>
            <p className="text-[10px] text-slate-400">Unified Kubernetes Management Platform</p>
          </div>
          <div className="ml-4 pl-4 border-l border-slate-700">
            <span className="text-xs text-slate-500">{formattedDate}</span>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-slate-400">Cluster:</label>
            {loading && clusters.length === 0 ? (
              <div className="px-3 py-2 text-sm text-slate-500">Loading...</div>
            ) : (
              <select
                value={activeCluster || ''}
                onChange={(e) => handleClusterChange(e.target.value)}
                className="bg-slate-800/60 border border-slate-600/50 rounded-lg px-3 py-2 text-sm font-medium text-white hover:border-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors"
              >
                {clusters.length === 0 ? (
                  <option value="">No Clusters Available</option>
                ) : (
                  <>
                    {activeCluster === null && (
                      <option value="">Select a Cluster</option>
                    )}
                    {clusters.map((cluster) => (
                      <option key={cluster.id} value={cluster.id}>
                        {cluster.name}
                      </option>
                    ))}
                  </>
                )}
              </select>
            )}
          </div>

          {activeCluster && (
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-slate-400">Namespace:</label>
              {namespaces.length === 0 ? (
                <div className="px-3 py-2 text-sm text-slate-500">default</div>
              ) : (
                <select
                  value={activeNamespace === '_all' ? '_all' : activeNamespace}
                  onChange={(e) => handleNamespaceChange(e.target.value)}
                  className="bg-slate-800/60 border border-slate-600/50 rounded-lg px-3 py-2 text-sm font-medium text-white hover:border-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors"
                >
                  <option value="default">default</option>
                  <option value="_all">All Namespaces</option>
                  {namespaces
                    .filter(ns => ns.name !== 'default')
                    .map((ns) => (
                      <option key={ns.name} value={ns.name}>
                        {ns.name}
                      </option>
                    ))}
                </select>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 pl-6 border-l border-slate-700">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-slate-400">Connected</span>
          </div>

          {auth && (
            <div className="flex items-center gap-4 pl-6 border-l border-slate-700">
              <div className="text-right">
                <p className="text-sm font-medium text-white">{auth.email}</p>
                <p className="text-xs text-slate-400 capitalize">{auth.role}</p>
              </div>
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 text-sm text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}