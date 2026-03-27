import React, { useEffect, useState } from 'react'
import { v1API } from '../api'
import { useAppContext } from '../context/AppContext'

export default function Clusters() {
  const [clusters, setClusters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newClusterName, setNewClusterName] = useState('')
  const [kubeconfigFile, setKubeconfigFile] = useState(null)
  const [kubeconfigPath, setKubeconfigPath] = useState('')
  const [saving, setSaving] = useState(false)
  
  const { activeCluster, selectCluster } = useAppContext()

  useEffect(() => {
    fetchClusters()
  }, [])

  const fetchClusters = async () => {
    try {
      setLoading(true)
      const response = await v1API.listClusters()
      setClusters(response.data || [])
      setError(null)
    } catch (err) {
      console.error('Error fetching clusters:', err)
      setError(err.response?.data?.detail || 'Failed to load clusters')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCluster = async (clusterId) => {
    try {
      await v1API.setCluster(clusterId)
      selectCluster(clusterId)
    } catch (err) {
      console.error('Error selecting cluster:', err)
    }
  }

  const handleAddCluster = async (e) => {
    e.preventDefault()
    
    if (!newClusterName.trim()) {
      setError('Cluster name is required')
      return
    }

    if (!kubeconfigFile && !kubeconfigPath.trim()) {
      setError('Please provide a kubeconfig file or path')
      return
    }

    try {
      setSaving(true)
      setError(null)

      let kubeconfigValue = kubeconfigPath
      
      if (kubeconfigFile) {
        kubeconfigValue = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = (e) => resolve(e.target.result)
          reader.onerror = reject
          reader.readAsText(kubeconfigFile)
        })
      }

      await v1API.addCluster({
        name: newClusterName,
        kubeconfig_path: kubeconfigValue
      })

      setNewClusterName('')
      setKubeconfigFile(null)
      setKubeconfigPath('')
      setShowAddForm(false)
      fetchClusters()
    } catch (err) {
      console.error('Error adding cluster:', err)
      setError(err.response?.data?.detail || 'Failed to add cluster')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCluster = async (clusterId, clusterName) => {
    if (!confirm(`Are you sure you want to delete cluster "${clusterName}"?`)) {
      return
    }

    try {
      await fetch(`/v1/clusters/${clusterId}`, {
        method: 'DELETE',
        credentials: 'include'
      })
      fetchClusters()
      
      if (activeCluster === clusterId) {
        selectCluster(null)
      }
    } catch (err) {
      console.error('Error deleting cluster:', err)
      setError(err.response?.data?.detail || 'Failed to delete cluster')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Clusters</h1>
          <p className="text-slate-400 mt-2">Manage your Kubernetes clusters</p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 transition-all"
        >
          {showAddForm ? 'Cancel' : 'Add Cluster'}
        </button>
      </div>

      {error && (
        <div className="glass-card p-4 border-red-500/30">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {showAddForm && (
        <div className="glass-card p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Add New Cluster</h2>
          <form onSubmit={handleAddCluster} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Cluster Name
              </label>
              <input
                type="text"
                value={newClusterName}
                onChange={(e) => setNewClusterName(e.target.value)}
                placeholder="my-cluster"
                className="input-dark w-full"
                required
              />
            </div>

            <div className="border-t border-slate-700/50 pt-4">
              <p className="text-sm font-medium text-slate-300 mb-2">Kubeconfig (choose one option):</p>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Option 1: Upload kubeconfig file</label>
                  <input
                    type="file"
                    accept=".yaml,.yml,.json"
                    onChange={(e) => setKubeconfigFile(e.target.files[0])}
                    className="input-dark w-full"
                  />
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-700"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-slate-800 text-slate-500">Or</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-1">Option 2: Paste kubeconfig path</label>
                  <input
                    type="text"
                    value={kubeconfigPath}
                    onChange={(e) => setKubeconfigPath(e.target.value)}
                    placeholder="C:\Users\admin\.kube\config"
                    className="input-dark w-full"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700/50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all"
              >
                {saving ? 'Adding...' : 'Add Cluster'}
              </button>
            </div>
          </form>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
        </div>
      )}

      {!loading && clusters.length === 0 && (
        <div className="glass-card p-12 text-center">
          <p className="text-slate-500">No clusters found. Add a cluster to get started.</p>
        </div>
      )}

      {!loading && clusters.length > 0 && (
        <div className="glass-card overflow-hidden">
          <table className="min-w-full divide-y divide-slate-700/50">
            <thead className="bg-slate-800/30">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                  Cluster Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/30">
              {clusters.map((cluster) => (
                <tr key={cluster.id} className="hover:bg-slate-700/20">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-white">{cluster.name}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {activeCluster === cluster.id ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-600/20 text-green-400 border border-green-500/30">
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-600/30 text-slate-300 border border-slate-500/50">
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      {activeCluster !== cluster.id && (
                        <button
                          onClick={() => handleSelectCluster(cluster.id)}
                          className="text-sm text-cyan-400 hover:text-cyan-300"
                        >
                          Select
                        </button>
                      )}
                      <button
                        onClick={() => handleDeleteCluster(cluster.id, cluster.name)}
                        className="text-sm text-red-400 hover:text-red-300"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}