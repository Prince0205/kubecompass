import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppContext } from '../context/AppContext'
import { v1API } from '../api'
import DetailOverlay from '../components/DetailOverlay'
import yaml from 'js-yaml'

export default function Namespaces() {
  const { activeCluster, activeNamespace, selectNamespace } = useAppContext()
  const [namespaces, setNamespaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedNamespace, setSelectedNamespace] = useState(null)
  const [showDetail, setShowDetail] = useState(false)
  const [namespaceDetail, setNamespaceDetail] = useState(null)
  const [namespaceEvents, setNamespaceEvents] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (!activeCluster) {
      setLoading(false)
      return
    }

    const fetchNamespaces = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await v1API.listNamespaces()
        setNamespaces(response.data || [])
      } catch (err) {
        console.error('Error fetching namespaces:', err)
        setError(err.response?.data?.detail || 'Failed to load namespaces')
      } finally {
        setLoading(false)
      }
    }

    fetchNamespaces()
  }, [activeCluster])

  const handleNamespaceClick = async (namespace) => {
    setSelectedNamespace(namespace)
    setShowDetail(true)
    setDetailLoading(true)
    setNamespaceEvents([])
    
    try {
      console.log('Fetching namespace details for:', namespace)
      const detailsRes = await v1API.getNamespaceDetails(namespace)
      console.log('Namespace details:', detailsRes.data)
      setNamespaceDetail(detailsRes.data)
      
      console.log('Fetching namespace events for:', namespace)
      const eventsRes = await v1API.getNamespaceEvents(namespace)
      console.log('Namespace events:', eventsRes.data)
      setNamespaceEvents(eventsRes.data || [])
    } catch (err) {
      console.error('Error fetching namespace details:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleSelectNamespace = async (namespaceName) => {
    try {
      await selectNamespace(namespaceName)
    } catch (err) {
      console.error('Error setting namespace:', err)
    }
  }

  const handleCloseDetail = () => {
    setShowDetail(false)
    setSelectedNamespace(null)
    setNamespaceDetail(null)
    setNamespaceEvents([])
  }

  const renderNamespaceOverlay = () => {
    if (detailLoading) {
      return (
        <div className="text-center py-8">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
          <p className="mt-2 text-slate-400">Loading...</p>
        </div>
      )
    }
    
    if (!namespaceDetail) {
      return <p className="text-slate-500">No data available</p>
    }
    
    return (
      <div className="space-y-6">
        <div>
          <h4 className="text-sm font-semibold text-white mb-3">Basic Information</h4>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-xs text-slate-400">Name</dt>
              <dd className="text-sm font-medium text-white">{namespaceDetail.name}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Status</dt>
              <dd className="text-sm font-medium text-white">{namespaceDetail.status}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Created</dt>
              <dd className="text-sm font-medium text-white">{namespaceDetail.creation_timestamp || 'N/A'}</dd>
            </div>
          </dl>
        </div>

        {namespaceDetail.labels && Object.keys(namespaceDetail.labels).length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Labels</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(namespaceDetail.labels).map(([key, value]) => (
                <span key={key} className="inline-flex items-center px-2 py-1 rounded bg-blue-600/20 text-xs text-cyan-400 border border-blue-500/30">
                  {key}: {value}
                </span>
              ))}
            </div>
          </div>
        )}

        {namespaceDetail.annotations && Object.keys(namespaceDetail.annotations).length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Annotations</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(namespaceDetail.annotations).map(([key, value]) => (
                <span key={key} className="inline-flex items-center px-2 py-1 rounded bg-slate-700/50 text-xs text-slate-300 border border-slate-600/50">
                  {key}: {value}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderNamespaceEvents = () => {
    if (detailLoading) {
      return (
        <div className="text-center py-8">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
          <p className="mt-2 text-slate-400">Loading...</p>
        </div>
      )
    }
    
    if (!namespaceEvents || namespaceEvents.length === 0) {
      return <p className="text-slate-500">No events found</p>
    }
    
    return (
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {namespaceEvents.slice(0, 50).map((event, idx) => (
          <div key={idx} className="p-3 bg-slate-800/50 rounded-lg text-sm border border-slate-700/50">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                event.type === 'Warning' ? 'bg-yellow-600/30 text-yellow-400' : 
                event.type === 'Normal' ? 'bg-green-600/30 text-green-400' : 'bg-slate-600/30 text-slate-300'
              }`}>
                {event.type || 'Normal'}
              </span>
              <span className="font-medium text-white">{event.reason}</span>
            </div>
            <p className="text-slate-300 mt-1">{event.message}</p>
            <div className="text-xs text-slate-500 mt-1">
              {event.involved_object_kind}: {event.involved_object} • {event.last_timestamp || 'N/A'}
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">No Cluster Selected</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header to view namespaces.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Namespaces</h1>
          <p className="text-slate-400 mt-2">
            Cluster: <span className="font-semibold text-cyan-400">{activeCluster}</span>
          </p>
        </div>
        <button
          onClick={() => navigate('/approvals')}
          className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 transition-all"
        >
          Request New Namespace
        </button>
      </div>

      {error && (
        <div className="glass-card p-4 border-red-500/30">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
        </div>
      )}

      {!loading && !error && (
        <div className="glass-card overflow-hidden">
          <table className="min-w-full divide-y divide-slate-700/50">
            <thead className="bg-slate-800/30">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                  Namespace Name
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
              {namespaces.length === 0 ? (
                <tr>
                  <td colSpan="3" className="px-6 py-12 text-center text-slate-500">
                    No namespaces found
                  </td>
                </tr>
              ) : (
                namespaces.map((ns) => (
                  <tr key={ns.name} className="hover:bg-slate-700/20">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => handleNamespaceClick(ns.name)}
                        className="text-sm font-medium text-cyan-400 hover:text-cyan-300"
                      >
                        {ns.name}
                      </button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-600/20 text-green-400 border border-green-500/30">
                        Active
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {activeNamespace === ns.name ? (
                        <span className="text-sm text-cyan-400 font-medium">Selected</span>
                      ) : (
                        <button
                          onClick={() => handleSelectNamespace(ns.name)}
                          className="text-sm text-cyan-400 hover:text-cyan-300"
                        >
                          Select
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <DetailOverlay
        isOpen={showDetail}
        title={selectedNamespace}
        data={namespaceDetail}
        loading={detailLoading}
        resourceType="namespaces"
        onClose={handleCloseDetail}
        customContent={{
          overview: renderNamespaceOverlay(),
          events: renderNamespaceEvents()
        }}
        customTabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'events', label: 'Events' },
        ]}
      />
    </div>
  )
}