/**
 * Helm Manager Page
 * Browse, install, upgrade, rollback, and uninstall Helm releases
 * Manage Helm chart repositories
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useAppContext } from '../context/AppContext'
import { helmAPI } from '../api'
import {
  ArrowPathIcon,
  PlusIcon,
  TrashIcon,
  ClockIcon,
  CubeIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ArrowUturnLeftIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline'

const STATUS_COLORS = {
  deployed: '#22c55e',
  failed: '#ef4444',
  pending_install: '#eab308',
  pending_upgrade: '#eab308',
  pending_rollback: '#eab308',
  uninstalling: '#6b7280',
  superseded: '#6b7280',
  uninstalled: '#6b7280',
}

function ReleaseRow({ release, onRollback, onUninstall, onViewDetails }) {
  const name = release.name || release.Name || ''
  const namespace = release.namespace || release.Namespace || ''
  const status = (release.status || release.Status || 'unknown').toLowerCase()
  const chart = release.chart || release.Chart || ''
  const appVersion = release.app_version || release.AppVersion || ''
  const revision = release.revision || release.Revision || ''
  const updated = release.updated || release.Updated || ''

  const statusColor = STATUS_COLORS[status] || '#6b7280'

  return (
    <tr className="border-b border-slate-700/50 hover:bg-slate-800/30 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <CubeIcon className="h-4 w-4 text-blue-400 flex-shrink-0" />
          <span className="text-sm font-medium text-white">{name}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-slate-400">{namespace}</td>
      <td className="px-4 py-3">
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
          style={{ color: statusColor, backgroundColor: `${statusColor}15` }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: statusColor }} />
          {status}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-slate-300">{chart}</td>
      <td className="px-4 py-3 text-sm text-slate-400">{appVersion}</td>
      <td className="px-4 py-3 text-sm text-slate-400">{revision}</td>
      <td className="px-4 py-3 text-sm text-slate-400">{updated}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <button
            onClick={() => onViewDetails(name, namespace)}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-cyan-400 transition-colors"
            title="View Details"
          >
            <DocumentTextIcon className="h-4 w-4" />
          </button>
          <button
            onClick={() => onRollback(name, namespace)}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-amber-400 transition-colors"
            title="Rollback"
          >
            <ArrowUturnLeftIcon className="h-4 w-4" />
          </button>
          <button
            onClick={() => onUninstall(name, namespace)}
            className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-red-400 transition-colors"
            title="Uninstall"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  )
}

function ReleaseDetailModal({ release, namespace, onClose }) {
  const [tab, setTab] = useState('values')
  const [data, setData] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        if (tab === 'history') {
          const res = await helmAPI.getHistory(release, namespace)
          setHistory(Array.isArray(res.data) ? res.data : [])
        } else {
          const fn = tab === 'values' ? helmAPI.getValues : tab === 'manifest' ? helmAPI.getManifest : helmAPI.getNotes
          const res = await fn(release, namespace)
          setData(res.data[tab === 'values' ? 'values' : tab === 'manifest' ? 'manifest' : 'notes'] || '')
        }
      } catch {
        setData('Failed to load')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [release, namespace, tab])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-800 border border-slate-700 rounded-xl w-[90vw] max-w-4xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700">
          <h3 className="text-lg font-semibold text-white">{release}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">&times;</button>
        </div>
        <div className="flex border-b border-slate-700 px-5">
          {['values', 'manifest', 'notes', 'history'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'border-cyan-500 text-cyan-400'
                  : 'border-transparent text-slate-400 hover:text-white'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-auto p-5">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-2 border-cyan-500 border-t-transparent" />
            </div>
          ) : tab === 'history' ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-600 text-slate-400 text-xs uppercase">
                    <th className="px-3 py-2">Rev</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Chart</th>
                    <th className="px-3 py-2">App Version</th>
                    <th className="px-3 py-2">Updated</th>
                    <th className="px-3 py-2">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={i} className="border-b border-slate-700/50">
                      <td className="px-3 py-2 text-slate-300">{h.revision || h.Revision || ''}</td>
                      <td className="px-3 py-2">
                        <span style={{ color: STATUS_COLORS[(h.status || h.Status || '').toLowerCase()] || '#6b7280' }}>
                          {h.status || h.Status || ''}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-300">{h.chart || h.Chart || ''}</td>
                      <td className="px-3 py-2 text-slate-400">{h.app_version || h.AppVersion || ''}</td>
                      <td className="px-3 py-2 text-slate-400">{h.updated || h.Updated || ''}</td>
                      <td className="px-3 py-2 text-slate-400">{h.description || h.Description || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono bg-slate-900/50 p-4 rounded-lg overflow-auto max-h-[50vh]">
              {data || '(empty)'}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Helm() {
  const { activeCluster, activeNamespace } = useAppContext()
  const [releases, setReleases] = useState([])
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  // Install modal
  const [showInstall, setShowInstall] = useState(false)
  const [installStep, setInstallStep] = useState(1) // 1=configure, 2=values
  const [installChart, setInstallChart] = useState('')
  const [installName, setInstallName] = useState('')
  const [installVersion, setInstallVersion] = useState('')
  const [installValues, setInstallValues] = useState('')
  const [installing, setInstalling] = useState(false)
  const [loadingValues, setLoadingValues] = useState(false)

  // Search
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)

  // Repos
  const [showRepos, setShowRepos] = useState(false)
  const [repoName, setRepoName] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [addingRepo, setAddingRepo] = useState(false)
  const [updatingRepos, setUpdatingRepos] = useState(false)

  // Detail modal
  const [detailRelease, setDetailRelease] = useState(null)
  const [detailNs, setDetailNs] = useState('')

  // Rollback modal
  const [showRollback, setShowRollback] = useState(false)
  const [rollbackRelease, setRollbackRelease] = useState('')
  const [rollbackNs, setRollbackNs] = useState('')
  const [rollbackRevision, setRollbackRevision] = useState('')
  const [rollbackHistory, setRollbackHistory] = useState([])
  const [rollingBack, setRollingBack] = useState(false)

  const [allNs, setAllNs] = useState(true)

  const clearMsgs = () => { setError(null); setSuccessMsg(null) }

  const fetchReleases = useCallback(async () => {
    if (!activeCluster) return
    setLoading(true)
    clearMsgs()
    try {
      const res = await helmAPI.listReleases(activeNamespace, allNs)
      setReleases(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load releases'
      setError(msg)
      setReleases([])
    } finally {
      setLoading(false)
    }
  }, [activeCluster, activeNamespace, allNs])

  const fetchRepos = useCallback(async () => {
    try {
      const res = await helmAPI.listRepos()
      setRepos(Array.isArray(res.data) ? res.data : [])
    } catch {
      setRepos([])
    }
  }, [])

  useEffect(() => {
    fetchReleases()
    fetchRepos()
  }, [fetchReleases, fetchRepos])

  const handleSearch = async () => {
    if (!searchKeyword.trim()) return
    setSearching(true)
    try {
      const res = await helmAPI.searchCharts(searchKeyword)
      setSearchResults(Array.isArray(res.data) ? res.data : [])
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleFetchValues = async () => {
    if (!installChart) return
    setLoadingValues(true)
    try {
      const res = await helmAPI.getChartValues(installChart, installVersion)
      setInstallValues(res.data?.values || '# No default values found\n')
      setInstallStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load chart values')
    } finally {
      setLoadingValues(false)
    }
  }

  const handleInstall = async () => {
    if (!installChart || !installName) return
    setInstalling(true)
    clearMsgs()
    try {
      await helmAPI.installRelease(installName, installChart, activeNamespace, installVersion, installValues)
      setSuccessMsg(`Release "${installName}" installed successfully`)
      setShowInstall(false)
      setInstallStep(1)
      setInstallChart('')
      setInstallName('')
      setInstallVersion('')
      setInstallValues('')
      fetchReleases()
    } catch (err) {
      setError(err.response?.data?.detail || 'Installation failed')
    } finally {
      setInstalling(false)
    }
  }

  const resetInstall = () => {
    setShowInstall(false)
    setInstallStep(1)
    setInstallChart('')
    setInstallName('')
    setInstallVersion('')
    setInstallValues('')
    setSearchResults([])
    setSearchKeyword('')
  }

  const handleAddRepo = async () => {
    if (!repoName || !repoUrl) return
    setAddingRepo(true)
    clearMsgs()
    try {
      await helmAPI.addRepo(repoName, repoUrl)
      setSuccessMsg(`Repository "${repoName}" added`)
      setRepoName('')
      setRepoUrl('')
      fetchRepos()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add repository')
    } finally {
      setAddingRepo(false)
    }
  }

  const handleRemoveRepo = async (name) => {
    clearMsgs()
    try {
      await helmAPI.removeRepo(name)
      setSuccessMsg(`Repository "${name}" removed`)
      fetchRepos()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove repository')
    }
  }

  const handleUpdateRepos = async () => {
    setUpdatingRepos(true)
    clearMsgs()
    try {
      await helmAPI.updateRepos()
      setSuccessMsg('Repositories updated')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update repositories')
    } finally {
      setUpdatingRepos(false)
    }
  }

  const openRollback = async (name, ns) => {
    setRollbackRelease(name)
    setRollbackNs(ns)
    setShowRollback(true)
    try {
      const res = await helmAPI.getHistory(name, ns)
      setRollbackHistory(Array.isArray(res.data) ? res.data : [])
    } catch {
      setRollbackHistory([])
    }
  }

  const handleRollback = async () => {
    if (!rollbackRevision) return
    setRollingBack(true)
    clearMsgs()
    try {
      await helmAPI.rollbackRelease(rollbackRelease, rollbackRevision, rollbackNs)
      setSuccessMsg(`Release "${rollbackRelease}" rolled back to revision ${rollbackRevision}`)
      setShowRollback(false)
      fetchReleases()
    } catch (err) {
      setError(err.response?.data?.detail || 'Rollback failed')
    } finally {
      setRollingBack(false)
    }
  }

  const handleUninstall = async (name, ns) => {
    if (!confirm(`Uninstall release "${name}"?`)) return
    clearMsgs()
    try {
      await helmAPI.uninstallRelease(name, ns)
      setSuccessMsg(`Release "${name}" uninstalled`)
      fetchReleases()
    } catch (err) {
      setError(err.response?.data?.detail || 'Uninstall failed')
    }
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Helm Manager</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Helm Manager</h1>
          <p className="text-slate-400 mt-1">Browse, install, upgrade, and rollback Helm releases</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={allNs}
              onChange={e => setAllNs(e.target.checked)}
              className="rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500"
            />
            All Namespaces
          </label>
          <button
            onClick={() => setShowRepos(true)}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors text-sm"
          >
            <GlobeAltIcon className="h-4 w-4" />
            Repos ({repos.length})
          </button>
          <button
            onClick={() => setShowInstall(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 transition-all text-sm font-medium"
          >
            <PlusIcon className="h-4 w-4" />
            Install Chart
          </button>
          <button
            onClick={fetchReleases}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors text-sm"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-slate-400 border-t-transparent" />
            ) : (
              <ArrowPathIcon className="h-4 w-4" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">{error}</div>
      )}
      {successMsg && (
        <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">{successMsg}</div>
      )}

      {/* Releases Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-700 text-xs uppercase text-slate-400 bg-slate-800/30">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Namespace</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Chart</th>
                <th className="px-4 py-3">App Version</th>
                <th className="px-4 py-3">Revision</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {releases.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center">
                    <CubeIcon className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-400">
                      {loading ? 'Loading releases...' : 'No Helm releases found in this namespace'}
                    </p>
                    <p className="text-slate-500 text-sm mt-1">
                      {!loading && 'Install a chart to get started'}
                    </p>
                  </td>
                </tr>
              ) : (
                releases.map((r, i) => (
                  <ReleaseRow
                    key={r.name || r.Name || i}
                    release={r}
                    onRollback={openRollback}
                    onUninstall={handleUninstall}
                    onViewDetails={(name, ns) => { setDetailRelease(name); setDetailNs(ns) }}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Install Modal */}
      {showInstall && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-[90vw] max-w-2xl max-h-[85vh] flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700 flex-shrink-0">
              <h3 className="text-lg font-semibold text-white">
                Install Helm Chart
                {installStep === 2 && <span className="text-sm text-slate-400 ml-2">— Step 2: Edit Values</span>}
              </h3>
              <button onClick={resetInstall} className="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>

            <div className="flex-1 overflow-auto p-6">
              {installStep === 1 ? (
                <>
                  {/* Step 1: Configure */}
                  {/* Search */}
                  <div className="mb-4">
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Search Charts</label>
                    <div className="flex gap-2">
                      <input
                        value={searchKeyword}
                        onChange={e => setSearchKeyword(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleSearch()}
                        placeholder="e.g. nginx, prometheus, mysql"
                        className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      />
                      <button
                        onClick={handleSearch}
                        disabled={searching}
                        className="px-3 py-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition-colors"
                      >
                        {searching ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-slate-400 border-t-transparent" />
                        ) : (
                          <MagnifyingGlassIcon className="h-4 w-4 text-slate-400" />
                        )}
                      </button>
                    </div>
                    {searchResults.length > 0 && (
                      <div className="mt-2 max-h-32 overflow-auto bg-slate-900 border border-slate-600 rounded-lg">
                        {searchResults.map((r, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              setInstallChart(r.name || r.Name || '')
                              setInstallVersion((r.version || r.Version || '').split('.').slice(0, 3).join('.'))
                              setSearchResults([])
                            }}
                            className="w-full text-left px-3 py-1.5 hover:bg-slate-700 text-sm text-slate-300 flex items-center justify-between"
                          >
                            <span>{r.name || r.Name || ''}</span>
                            <span className="text-slate-500 text-xs">{r.version || r.Version || ''}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Release Name *</label>
                      <input
                        value={installName}
                        onChange={e => setInstallName(e.target.value)}
                        placeholder="my-release"
                        className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Chart *</label>
                      <input
                        value={installChart}
                        onChange={e => setInstallChart(e.target.value)}
                        placeholder="bitnami/nginx"
                        className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Version (optional)</label>
                      <input
                        value={installVersion}
                        onChange={e => setInstallVersion(e.target.value)}
                        placeholder="latest"
                        className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* Step 2: Edit Values */}
                  <div className="mb-3 text-xs text-slate-400">
                    Chart: <span className="text-white font-medium">{installChart}</span>
                    {installVersion && <span> @ {installVersion}</span>}
                    {' — '}Release: <span className="text-white font-medium">{installName}</span>
                  </div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    values.yaml
                    <span className="font-normal text-slate-500 ml-1">(edit to customize your installation)</span>
                  </label>
                  <textarea
                    value={installValues}
                    onChange={e => setInstallValues(e.target.value)}
                    rows={20}
                    spellCheck={false}
                    className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-xs text-slate-200 font-mono focus:ring-2 focus:ring-cyan-500 focus:border-transparent resize-y"
                    style={{ minHeight: '400px' }}
                  />
                </>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-700 flex-shrink-0">
              {installStep === 1 ? (
                <>
                  <button
                    onClick={resetInstall}
                    className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleFetchValues}
                    disabled={loadingValues || !installChart || !installName}
                    className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all text-sm font-medium"
                  >
                    {loadingValues && <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />}
                    Next: Edit Values
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => setInstallStep(1)}
                    className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleInstall}
                    disabled={installing}
                    className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all text-sm font-medium"
                  >
                    {installing && <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />}
                    Install
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Repos Modal */}
      {showRepos && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-[90vw] max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Helm Repositories</h3>
              <button onClick={() => setShowRepos(false)} className="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>

            <div className="flex gap-2 mb-4">
              <input
                value={repoName}
                onChange={e => setRepoName(e.target.value)}
                placeholder="Name"
                className="w-1/3 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500"
              />
              <input
                value={repoUrl}
                onChange={e => setRepoUrl(e.target.value)}
                placeholder="https://charts.example.com"
                className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500"
              />
              <button
                onClick={handleAddRepo}
                disabled={addingRepo || !repoName || !repoUrl}
                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:opacity-50 transition-colors text-sm"
              >
                {addingRepo ? '...' : 'Add'}
              </button>
            </div>

            <div className="flex justify-end mb-3">
              <button
                onClick={handleUpdateRepos}
                disabled={updatingRepos}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-700 text-slate-300 rounded hover:bg-slate-600 transition-colors"
              >
                {updatingRepos ? (
                  <div className="animate-spin rounded-full h-3 w-3 border border-slate-400 border-t-transparent" />
                ) : (
                  <ArrowPathIcon className="h-3 w-3" />
                )}
                Update All Repos
              </button>
            </div>

            <div className="max-h-60 overflow-auto">
              {repos.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-6">No repositories configured</p>
              ) : (
                repos.map((repo, i) => (
                  <div key={i} className="flex items-center justify-between px-3 py-2 border-b border-slate-700/50 hover:bg-slate-700/30">
                    <div>
                      <p className="text-sm text-white font-medium">{repo.name || repo.Name || ''}</p>
                      <p className="text-xs text-slate-500">{repo.url || repo.URL || ''}</p>
                    </div>
                    <button
                      onClick={() => handleRemoveRepo(repo.name || repo.Name)}
                      className="p-1.5 rounded hover:bg-slate-600 text-slate-400 hover:text-red-400 transition-colors"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Rollback Modal */}
      {showRollback && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-800 border border-slate-700 rounded-xl w-[90vw] max-w-md p-6">
            <h3 className="text-lg font-semibold text-white mb-1">Rollback Release</h3>
            <p className="text-sm text-slate-400 mb-4">{rollbackRelease}</p>

            <label className="block text-xs font-semibold text-slate-400 mb-1">Select Revision</label>
            <select
              value={rollbackRevision}
              onChange={e => setRollbackRevision(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-cyan-500 mb-4"
            >
              <option value="">-- Select revision --</option>
              {rollbackHistory.map((h, i) => (
                <option key={i} value={h.revision || h.Revision || ''}>
                  Rev {h.revision || h.Revision || ''} - {h.chart || h.Chart || ''} ({h.status || h.Status || ''}) - {h.updated || h.Updated || ''}
                </option>
              ))}
            </select>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowRollback(false)}
                className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleRollback}
                disabled={rollingBack || !rollbackRevision}
                className="flex items-center gap-2 px-5 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-500 disabled:opacity-50 transition-all text-sm font-medium"
              >
                {rollingBack && <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />}
                Rollback
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {detailRelease && (
        <ReleaseDetailModal
          release={detailRelease}
          namespace={detailNs}
          onClose={() => setDetailRelease(null)}
        />
      )}
    </div>
  )
}
