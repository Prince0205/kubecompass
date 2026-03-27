import React, { useState, useEffect } from 'react'
import { useAppContext } from '../context/AppContext'
import { namespaceRequestsAPI } from '../api'

export default function Approvals() {
  const { activeCluster, auth } = useAppContext()
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    cpu_limit: '2',
    memory_limit: '4Gi',
    storage_limit: '10Gi',
    pods_limit: 10,
    services_limit: 10,
    configmaps_limit: 10,
    secrets_limit: 10,
  })
  const [saving, setSaving] = useState(false)
  const [actionInProgress, setActionInProgress] = useState(null)

  const isAdmin = auth?.role === 'admin'

  useEffect(() => {
    if (activeCluster) {
      fetchRequests()
    }
  }, [activeCluster])

  const fetchRequests = async () => {
    try {
      setLoading(true)
      const response = await namespaceRequestsAPI.list()
      setRequests(response.data || [])
      setError(null)
    } catch (err) {
      console.error('Error fetching requests:', err)
      setError(err.response?.data?.detail || 'Failed to load requests')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setError('Namespace name is required')
      return
    }

    try {
      setSaving(true)
      setError(null)
      await namespaceRequestsAPI.create(formData)
      setShowForm(false)
      setFormData({
        name: '',
        description: '',
        cpu_limit: '2',
        memory_limit: '4Gi',
        storage_limit: '10Gi',
        pods_limit: 10,
        services_limit: 10,
        configmaps_limit: 10,
        secrets_limit: 10,
      })
      fetchRequests()
    } catch (err) {
      console.error('Error creating request:', err)
      setError(err.response?.data?.detail || 'Failed to create request')
    } finally {
      setSaving(false)
    }
  }

  const handleAction = async (id, action, comment = '') => {
    try {
      setActionInProgress(id)
      await namespaceRequestsAPI.approve(id, action, comment)
      fetchRequests()
    } catch (err) {
      console.error('Error processing request:', err)
      setError(err.response?.data?.detail || `Failed to ${action} request`)
    } finally {
      setActionInProgress(null)
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'bg-yellow-600/30 text-yellow-400 border border-yellow-500/30'
      case 'approved': return 'bg-green-600/30 text-green-400 border border-green-500/30'
      case 'rejected': return 'bg-red-600/30 text-red-400 border border-red-500/30'
      case 'failed': return 'bg-red-600/30 text-red-400 border border-red-500/30'
      default: return 'bg-slate-600/30 text-slate-300 border border-slate-500/50'
    }
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">No Cluster Selected</h2>
        <p className="text-slate-400 mt-2">Please select a cluster to view namespace requests.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Namespace Requests</h1>
          <p className="text-slate-400 mt-2">
            Cluster: <span className="font-semibold text-cyan-400">{activeCluster}</span>
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 transition-all"
        >
          {showForm ? 'Cancel' : 'Request Namespace'}
        </button>
      </div>

      {error && (
        <div className="glass-card p-4 border-red-500/30">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {showForm && (
        <div className="glass-card p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Request New Namespace</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Namespace Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-') })}
                  placeholder="my-namespace"
                  className="input-dark w-full"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Description</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Purpose of this namespace"
                  className="input-dark w-full"
                />
              </div>
            </div>

            <div className="border-t border-slate-700/50 pt-4">
              <h3 className="text-sm font-semibold text-white mb-3">Resource Quotas</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">CPU Limit</label>
                  <input
                    type="text"
                    value={formData.cpu_limit}
                    onChange={(e) => setFormData({ ...formData, cpu_limit: e.target.value })}
                    placeholder="2"
                    className="input-dark w-full text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Memory Limit</label>
                  <input
                    type="text"
                    value={formData.memory_limit}
                    onChange={(e) => setFormData({ ...formData, memory_limit: e.target.value })}
                    placeholder="4Gi"
                    className="input-dark w-full text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Storage Limit</label>
                  <input
                    type="text"
                    value={formData.storage_limit}
                    onChange={(e) => setFormData({ ...formData, storage_limit: e.target.value })}
                    placeholder="10Gi"
                    className="input-dark w-full text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Pods Limit</label>
                  <input
                    type="number"
                    value={formData.pods_limit}
                    onChange={(e) => setFormData({ ...formData, pods_limit: parseInt(e.target.value) || 0 })}
                    placeholder="10"
                    className="input-dark w-full text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Services Limit</label>
                  <input
                    type="number"
                    value={formData.services_limit}
                    onChange={(e) => setFormData({ ...formData, services_limit: parseInt(e.target.value) || 0 })}
                    placeholder="10"
                    className="input-dark w-full text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">ConfigMaps Limit</label>
                  <input
                    type="number"
                    value={formData.configmaps_limit}
                    onChange={(e) => setFormData({ ...formData, configmaps_limit: parseInt(e.target.value) || 0 })}
                    placeholder="10"
                    className="input-dark w-full text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Secrets Limit</label>
                  <input
                    type="number"
                    value={formData.secrets_limit}
                    onChange={(e) => setFormData({ ...formData, secrets_limit: parseInt(e.target.value) || 0 })}
                    placeholder="10"
                    className="input-dark w-full text-sm"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700/50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all"
              >
                {saving ? 'Submitting...' : 'Submit Request'}
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

      {!loading && requests.length === 0 && (
        <div className="glass-card p-12 text-center">
          <p className="text-slate-500">No namespace requests found.</p>
        </div>
      )}

      {!loading && requests.length > 0 && (
        <div className="glass-card overflow-hidden">
          <table className="min-w-full divide-y divide-slate-700/50">
            <thead className="bg-slate-800/30">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Requested By</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Quotas</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Date</th>
                {isAdmin && <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/30">
              {requests.map((req) => (
                <tr key={req.id} className="hover:bg-slate-700/20">
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-white">{req.name}</div>
                    {req.description && <div className="text-xs text-slate-500">{req.description}</div>}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">{req.requested_by}</td>
                  <td className="px-6 py-4 text-xs text-slate-500">
                    <div>CPU: {req.cpu_limit}</div>
                    <div>Mem: {req.memory_limit}</div>
                    <div>Storage: {req.storage_limit}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(req.status)}`}>
                      {req.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-400">
                    {req.created_at ? new Date(req.created_at).toLocaleDateString() : '-'}
                  </td>
                  {isAdmin && (
                    <td className="px-6 py-4">
                      {req.status === 'pending' && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAction(req.id, 'approve')}
                            disabled={actionInProgress === req.id}
                            className="px-3 py-1 text-xs bg-green-600/30 text-green-400 border border-green-500/30 rounded hover:bg-green-600/50 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleAction(req.id, 'reject')}
                            disabled={actionInProgress === req.id}
                            className="px-3 py-1 text-xs bg-red-600/30 text-red-400 border border-red-500/30 rounded hover:bg-red-600/50 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}