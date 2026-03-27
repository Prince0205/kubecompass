import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { PlusIcon } from '@heroicons/react/24/outline'
import ResourceList from '../components/ResourceList'
import DetailOverlay from '../components/DetailOverlay'
import CreateResource from '../components/CreateResource'
import { useFetchList, useFetchDetail } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import apiClient, { configAPI, v1API } from '../api'

const rbacAPI = {
  listRoles: () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.roles || [] })),
  listClusterRoles: () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.clusterroles || [] })),
  listRoleBindings: () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.bindings || [] })),
  listClusterRoleBindings: () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.clusterrolebindings || [] })),
}

const RBAC_CLUSTER_SCOPED = ['clusterroles', 'clusterrolebindings']

export default function RBACResources() {
  const location = useLocation()
  const { activeCluster, activeNamespace, setClusterScoped, selectNamespace, lastNamespacedNamespace } = useAppContext()
  const [selectedResource, setSelectedResource] = useState(null)
  const [showDetail, setShowDetail] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const isFirstRender = useRef(true)
  
  const path = location.pathname
  
  const resourceConfig = useMemo(() => {
    if (path.includes('/clusterroles')) {
      return {
        resourceType: 'clusterroles',
        apiCall: rbacAPI.listClusterRoles,
        title: 'ClusterRoles',
        columns: [{ key: 'metadata.name', label: 'Name' }],
      }
    } else if (path.includes('/rolebindings')) {
      return {
        resourceType: 'rolebindings',
        apiCall: rbacAPI.listRoleBindings,
        title: 'Role Bindings',
        columns: [
          { key: 'metadata.name', label: 'Name' },
          { key: 'metadata.namespace', label: 'Namespace' },
        ],
      }
    } else if (path.includes('/clusterrolebindings')) {
      return {
        resourceType: 'clusterrolebindings',
        apiCall: rbacAPI.listClusterRoleBindings,
        title: 'ClusterRole Bindings',
        columns: [{ key: 'metadata.name', label: 'Name' }],
      }
    } else if (path.includes('/serviceaccounts')) {
      return {
        resourceType: 'serviceaccounts',
        apiCall: configAPI.listServiceAccounts,
        title: 'Service Accounts',
        columns: [
          { key: 'name', label: 'Name' },
          { key: 'namespace', label: 'Namespace' },
        ],
      }
    }
    return {
      resourceType: 'roles',
      apiCall: rbacAPI.listRoles,
      title: 'Roles',
      columns: [
        { key: 'metadata.name', label: 'Name' },
        { key: 'metadata.namespace', label: 'Namespace' },
      ],
    }
  }, [path])

  const { resourceType, apiCall, title, columns } = resourceConfig

  const getCreateType = () => {
    const mapping = {
      'roles': 'role',
      'clusterroles': 'clusterrole',
      'rolebindings': 'rolebinding',
      'clusterrolebindings': 'clusterrolebinding',
      'serviceaccounts': 'serviceaccount',
    }
    return mapping[resourceType] || resourceType
  }

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    
    const isClusterScopedResource = RBAC_CLUSTER_SCOPED.includes(resourceType)
    
    if (isClusterScopedResource && activeNamespace !== '_all') {
      setClusterScoped(true)
    } else if (!isClusterScopedResource && activeNamespace === '_all' && lastNamespacedNamespace) {
      selectNamespace(lastNamespacedNamespace)
    }
  }, [resourceType, activeNamespace, setClusterScoped, selectNamespace, lastNamespacedNamespace])

  const [fetchKey, setFetchKey] = useState(0)
  
  const { data: resources, loading, error, refetch: refetchResources } = useFetchList(
    apiCall,
    `rbac-${resourceType}-${activeCluster}-${activeNamespace}`,
    [activeCluster, activeNamespace, resourceType],
    fetchKey
  )

  const { data: detailData, loading: detailLoading } = useFetchDetail(
    selectedResource ? () => {
      const resourceName = selectedResource.name || selectedResource.metadata?.name
      if (!resourceName) return Promise.resolve(null)
      
      if (resourceType === 'serviceaccounts') return configAPI.getServiceAccount(resourceName)
      if (resourceType === 'roles') return v1API.getRole(resourceName)
      if (resourceType === 'rolebindings') return v1API.getRoleBinding(resourceName)
      if (resourceType === 'clusterroles') return v1API.getClusterRole(resourceName)
      if (resourceType === 'clusterrolebindings') return v1API.getClusterRoleBinding(resourceName)
      return Promise.resolve(null)
    } : null,
    `rbac-detail-${resourceType}-${selectedResource?.name || selectedResource?.metadata?.name}`
  )

  const handleRowClick = (resource) => {
    setSelectedResource(resource)
    setShowDetail(true)
  }

  const displayNamespace = activeNamespace === '_all' ? 'All' : activeNamespace

  const displayData = detailData || selectedResource

  const handleDelete = async (name) => {
    try {
      const resourceName = name || selectedResource?.name || selectedResource?.metadata?.name
      if (!resourceName) throw new Error('No resource name')
      await v1API.deleteResource(resourceType, resourceName)
      refetchResources()
    } catch (err) {
      console.error('Error deleting:', err)
      throw err
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{title}</h1>
          <p className="text-slate-400 mt-2">
            Namespace: <span className="font-semibold text-cyan-400">{displayNamespace}</span>
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 transition-all"
        >
          <PlusIcon className="h-5 w-5" />
          Create
        </button>
      </div>

      <ResourceList
        title={title}
        items={resources}
        columns={columns}
        loading={loading}
        error={error}
        resourceType={resourceType}
        onRowClick={handleRowClick}
      />

      {showDetail && selectedResource && (
        <DetailOverlay
          isOpen={showDetail}
          title={selectedResource?.metadata?.name || selectedResource?.name}
          data={displayData}
          loading={detailLoading}
          resourceType={resourceType}
          fetchYaml={(resourceType, name) => v1API.getResourceYaml(resourceType, name)}
          onDelete={handleDelete}
          onClose={() => { setShowDetail(false); setSelectedResource(null); }}
        />
      )}

      <CreateResource
        isOpen={showCreate}
        resourceType={getCreateType()}
        onClose={() => setShowCreate(false)}
        onSuccess={() => { setShowCreate(false); refetchResources(); }}
      />
    </div>
  )
}