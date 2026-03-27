import React, { useState, useEffect } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import ResourceList from '../components/ResourceList'
import DetailOverlay from '../components/DetailOverlay'
import CreateResource from '../components/CreateResource'
import { useFetchList, useFetchDetail } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import { PlusIcon } from '@heroicons/react/24/outline'
import apiClient from '../api'
import {
  workloadAPI,
  configAPI,
  networkAPI,
  storageAPI,
  crdAPI,
  v1API,
} from '../api'

// Cluster-scoped resources
const CLUSTER_SCOPED_TYPES = ['clusterroles', 'clusterrolebindings', 'storageclasses', 'pvs', 'nodes']

export default function Resources() {
  const location = useLocation()
  const navigate = useNavigate()
  const { plural: crdPlural } = useParams()
  const { activeCluster, activeNamespace, setClusterScoped, selectNamespace, lastNamespacedNamespace } = useAppContext()
  const [selectedResource, setSelectedResource] = useState(null)
  const [showDetail, setShowDetail] = useState(false)
  const isFirstRender = React.useRef(true)

  // CRD instance state
  const [crdMeta, setCrdMeta] = useState(location.state?.crdMeta || null)
  const [crdMetaLoading, setCrdMetaLoading] = useState(false)

  // Determine resource type from route
  const path = location.pathname
  let resourceType = 'pods'
  let apiCall = workloadAPI.listPods
  let columns = []
  let title = 'Resources'
  let isCustomResourceInstance = false

  // Check if this is a custom resource instance view (/crds/:plural)
  if (crdPlural) {
    isCustomResourceInstance = true
    resourceType = 'custom_resource'
    title = crdMeta?.kind || crdPlural

    if (crdMeta) {
      const isClusterScoped = crdMeta.scope === 'Cluster'
      // versions can be array of strings (from list endpoint) or array of objects (from detail endpoint)
      let version = 'v1'
      if (Array.isArray(crdMeta.versions) && crdMeta.versions.length > 0) {
        const first = crdMeta.versions[0]
        if (typeof first === 'string') {
          version = first
        } else if (typeof first === 'object' && first !== null) {
          version = crdMeta.versions.find(v => v.storage)?.name || first.name || 'v1'
        }
      }

      if (isClusterScoped) {
        apiCall = () => crdAPI.listClusterCustomResources(crdMeta.group, version, crdMeta.plural)
      } else {
        apiCall = () => crdAPI.listCustomResources(crdMeta.group, version, crdMeta.plural)
      }
    } else {
      // Placeholder until CRD meta is loaded
      apiCall = () => Promise.resolve({ data: { custom_resources: [] } })
    }

    columns = [
      { key: 'name', label: 'Name' },
      { key: 'namespace', label: 'Namespace' },
      { key: 'kind', label: 'Kind' },
      { key: 'created', label: 'Age' },
    ]
  } else if (path.includes('/workload/pods')) {
    resourceType = 'pods'
    apiCall = workloadAPI.listPods
    title = 'Pods'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'status', label: 'Status' },
      { key: 'ready', label: 'Ready' },
      { key: 'restarts', label: 'Restarts' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/workload/deployments')) {
    resourceType = 'deployments'
    apiCall = workloadAPI.listDeployments
    title = 'Deployments'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'ready', label: 'Ready' },
      { key: 'up_to_date', label: 'Up-to-date' },
      { key: 'available', label: 'Available' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/workload/replicasets')) {
    resourceType = 'replicasets'
    apiCall = workloadAPI.listReplicaSets
    title = 'ReplicaSets'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'ready', label: 'Ready' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/workload/statefulsets')) {
    resourceType = 'statefulsets'
    apiCall = workloadAPI.listStatefulSets
    title = 'StatefulSets'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'ready', label: 'Ready' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/workload/daemonsets')) {
    resourceType = 'daemonsets'
    apiCall = workloadAPI.listDaemonSets
    title = 'DaemonSets'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'ready', label: 'Ready' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/workload/jobs')) {
    resourceType = 'jobs'
    apiCall = workloadAPI.listJobs
    title = 'Jobs'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'status', label: 'Status' },
      { key: 'completions', label: 'Completions' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/workload/cronjobs')) {
    resourceType = 'cronjobs'
    apiCall = workloadAPI.listCronJobs
    title = 'CronJobs'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'schedule', label: 'Schedule' },
      { key: 'suspend', label: 'Suspend' },
      { key: 'active', label: 'Active' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/config/configmaps')) {
    resourceType = 'configmaps'
    apiCall = configAPI.listConfigMaps
    title = 'ConfigMaps'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'data_keys', label: 'Keys' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/config/secrets')) {
    resourceType = 'secrets'
    apiCall = configAPI.listSecrets
    title = 'Secrets'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/config/hpas')) {
    resourceType = 'hpas'
    apiCall = configAPI.listHPAs
    title = 'Horizontal Pod Autoscalers'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'min_replicas', label: 'Min' },
      { key: 'max_replicas', label: 'Max' },
      { key: 'replicas', label: 'Current' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/config/quotas')) {
    resourceType = 'quotas'
    apiCall = configAPI.listResourceQuotas
    title = 'Resource Quotas'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/config/limitranges')) {
    resourceType = 'limitranges'
    apiCall = configAPI.listLimitRanges
    title = 'Limit Ranges'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/network/services')) {
    resourceType = 'services'
    apiCall = networkAPI.listServices
    title = 'Services'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'cluster_ip', label: 'Cluster IP' },
      { key: 'external_ip', label: 'External IP' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/network/endpoints')) {
    resourceType = 'endpoints'
    apiCall = networkAPI.listEndpoints
    title = 'Endpoints'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'endpoints', label: 'Endpoints' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/network/ingresses')) {
    resourceType = 'ingresses'
    apiCall = networkAPI.listIngresses
    title = 'Ingresses'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'hosts', label: 'Hosts' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/network/policies')) {
    resourceType = 'networkpolicies'
    apiCall = networkAPI.listNetworkPolicies
    title = 'Network Policies'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'pod_selector', label: 'Pod Selector' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/storage/pvcs')) {
    resourceType = 'pvcs'
    apiCall = storageAPI.listPersistentVolumeClaims
    title = 'PersistentVolumeClaims'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'status', label: 'Status' },
      { key: 'capacity', label: 'Capacity' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/storage/pvs')) {
    resourceType = 'pvs'
    apiCall = storageAPI.listPersistentVolumes
    title = 'PersistentVolumes'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'capacity', label: 'Capacity' },
      { key: 'status', label: 'Status' },
      { key: 'claim', label: 'Claim' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/storage/classes')) {
    resourceType = 'storageclasses'
    apiCall = storageAPI.listStorageClasses
    title = 'Storage Classes'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'provisioner', label: 'Provisioner' },
      { key: 'reclaim_policy', label: 'Reclaim Policy' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path === '/crds') {
    resourceType = 'crds'
    apiCall = crdAPI.listCRDs
    title = 'Custom Resource Definitions'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'group', label: 'Group' },
      { key: 'kind', label: 'Kind' },
      { key: 'scope', label: 'Scope' },
      { key: 'versions', label: 'Versions' },
      { key: 'age', label: 'Age' },
    ]
  } else if (path.includes('/rbac/roles')) {
    resourceType = 'roles'
    apiCall = () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.roles || [] }))
    title = 'Roles'
    columns = [
      { key: 'metadata.name', label: 'Name' },
      { key: 'metadata.namespace', label: 'Namespace' },
      { key: 'metadata.creationTimestamp', label: 'Age' },
    ]
  } else if (path.includes('/rbac/clusterroles')) {
    resourceType = 'clusterroles'
    apiCall = () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.clusterroles || [] }))
    title = 'ClusterRoles'
    columns = [
      { key: 'metadata.name', label: 'Name' },
      { key: 'metadata.creationTimestamp', label: 'Age' },
    ]
  } else if (path.includes('/rbac/rolebindings')) {
    resourceType = 'rolebindings'
    apiCall = () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.bindings || [] }))
    title = 'Role Bindings'
    columns = [
      { key: 'metadata.name', label: 'Name' },
      { key: 'metadata.namespace', label: 'Namespace' },
    ]
  } else if (path.includes('/rbac/clusterrolebindings')) {
    resourceType = 'clusterrolebindings'
    apiCall = () => apiClient.get('/v1/rbac').then(r => ({ data: r.data.clusterrolebindings || [] }))
    title = 'ClusterRole Bindings'
    columns = [
      { key: 'metadata.name', label: 'Name' },
    ]
  } else if (path.includes('/rbac/serviceaccounts')) {
    resourceType = 'serviceaccounts'
    apiCall = () => apiClient.get('/api/resources/config/serviceaccounts').then(r => ({ data: r.data }))
    title = 'Service Accounts'
    columns = [
      { key: 'name', label: 'Name' },
      { key: 'namespace', label: 'Namespace' },
      { key: 'age', label: 'Age' },
    ]
  }

  // Fetch CRD metadata when viewing custom resource instances but metadata not available via state
  useEffect(() => {
    if (crdPlural && !crdMeta && activeCluster) {
      setCrdMetaLoading(true)
      crdAPI.listCRDs().then(response => {
        const crds = response.data?.crds || []
        const found = crds.find(c => c.plural === crdPlural)
        if (found) {
          setCrdMeta(found)
        }
      }).catch(err => {
        console.error('Error fetching CRD metadata:', err)
      }).finally(() => {
        setCrdMetaLoading(false)
      })
    }
  }, [crdPlural, activeCluster])

  // Reset crdMeta when plural changes (different CRD selected)
  useEffect(() => {
    if (location.state?.crdMeta) {
      setCrdMeta(location.state.crdMeta)
    } else if (crdPlural) {
      // Will be fetched by the effect above
      setCrdMeta(null)
    }
  }, [crdPlural])

  // Handle cluster-scoped resources - switch namespace dropdown to "All" and restore when leaving
  useEffect(() => {
    // Skip on first render to avoid flickering
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    
    const isClusterScopedResource = CLUSTER_SCOPED_TYPES.includes(resourceType) ||
      (isCustomResourceInstance && crdMeta?.scope === 'Cluster')
    
    if (isClusterScopedResource && activeNamespace !== '_all') {
      // Switch to cluster-scoped mode
      setClusterScoped(true)
    } else if (!isClusterScopedResource && activeNamespace === '_all' && lastNamespacedNamespace) {
      // Restore last used namespace when going back to namespaced resources
      selectNamespace(lastNamespacedNamespace)
    }
  }, [resourceType, activeNamespace, crdMeta?.scope])

  const [fetchKey, setFetchKey] = useState(0)

  // Build a stable cache key for custom resource instances
  const crdCacheKey = isCustomResourceInstance
    ? `resources-${activeCluster}-custom-${crdMeta?.group}-${crdMeta?.plural}-${activeNamespace}`
    : `resources-${activeCluster}-${resourceType}-${activeNamespace}`

  const { data: resources, loading, error, refetch: refetchResources } = useFetchList(
    apiCall,
    crdCacheKey,
    [activeCluster, activeNamespace, resourceType, crdMeta?.group, crdMeta?.plural],
    fetchKey
  )

  const { data: detailData, loading: detailLoading } = useFetchDetail(
    selectedResource ? () => {
      const resourceName = selectedResource.name
      if (!resourceName) return Promise.resolve({})
      
      if (resourceType === 'pods') return workloadAPI.getPod(resourceName)
      if (resourceType === 'deployments') return workloadAPI.getDeployment(resourceName)
      if (resourceType === 'replicasets') return workloadAPI.getReplicaSet(resourceName)
      if (resourceType === 'statefulsets') return workloadAPI.getStatefulSet(resourceName)
      if (resourceType === 'daemonsets') return workloadAPI.getDaemonSet(resourceName)
      if (resourceType === 'jobs') return workloadAPI.getJob(resourceName)
      if (resourceType === 'cronjobs') return workloadAPI.getCronJob(resourceName)
      if (resourceType === 'configmaps') return configAPI.getConfigMap(resourceName)
      if (resourceType === 'secrets') return configAPI.getSecret(resourceName)
      if (resourceType === 'hpas') return configAPI.getHPA(resourceName)
      if (resourceType === 'quotas') return configAPI.getResourceQuota(resourceName)
      if (resourceType === 'limitranges') return configAPI.getLimitRange(resourceName)
      if (resourceType === 'services') return networkAPI.getService(resourceName)
      if (resourceType === 'endpoints') return v1API.getEndpoints(resourceName)
      if (resourceType === 'ingresses') return networkAPI.getIngress(resourceName)
      if (resourceType === 'networkpolicies') return networkAPI.getNetworkPolicy(resourceName)
      if (resourceType === 'pvcs') return storageAPI.getPersistentVolumeClaim(resourceName)
      if (resourceType === 'pvs') return storageAPI.getPersistentVolume(resourceName)
      if (resourceType === 'storageclasses') return storageAPI.getStorageClass(resourceName)
      if (resourceType === 'crds') return crdAPI.getCRD(resourceName)
      if (resourceType === 'custom_resource' && crdMeta) {
        const isClusterScoped = crdMeta.scope === 'Cluster'
        let version = 'v1'
        if (Array.isArray(crdMeta.versions) && crdMeta.versions.length > 0) {
          const first = crdMeta.versions[0]
          if (typeof first === 'string') {
            version = first
          } else if (typeof first === 'object' && first !== null) {
            version = crdMeta.versions.find(v => v.storage)?.name || first.name || 'v1'
          }
        }
        if (isClusterScoped) {
          return crdAPI.getClusterCustomResource(crdMeta.group, version, crdMeta.plural, resourceName)
        }
        return crdAPI.getCustomResource(crdMeta.group, version, crdMeta.plural, resourceName)
      }
      return Promise.resolve({})
    } : null,
    `resource-detail-${resourceType}-${selectedResource?.name}`
  )

  const handleRowClick = (resource) => {
    setSelectedResource(resource)
    setShowDetail(true)
  }

  const handleScale = async (name, replicas, containerIndex = null, newImage = null) => {
    try {
      if (resourceType === 'deployments') {
        if (newImage !== null && containerIndex !== null) {
          await workloadAPI.updateDeploymentImage(name, containerIndex, newImage)
        } else {
          await workloadAPI.scaleDeployment(name, replicas)
        }
      } else if (resourceType === 'statefulsets') {
        await workloadAPI.scaleStatefulSet(name, replicas)
      }
      setSelectedResource({ ...selectedResource })
      refetchResources()
    } catch (err) {
      console.error('Error scaling:', err)
      throw err
    }
  }

  const handleSave = async (name, data) => {
    try {
      if (resourceType === 'configmaps') {
        await configAPI.editConfigMap(name, data)
      } else if (resourceType === 'secrets') {
        await configAPI.editSecret(name, data)
      }
      setSelectedResource({ ...selectedResource })
      refetchResources()
    } catch (err) {
      console.error('Error saving:', err)
      throw err
    }
  }

  const handleDelete = async (name) => {
    try {
      const resourceName = name || selectedResource?.name
      if (!resourceName) throw new Error('No resource name')
      
      if (resourceType === 'pods') {
        await workloadAPI.deletePod(resourceName)
      } else if (resourceType === 'deployments') {
        await workloadAPI.deleteDeployment(resourceName)
      } else if (resourceType === 'statefulsets') {
        await workloadAPI.deleteStatefulSet(resourceName)
      } else if (resourceType === 'daemonsets') {
        await workloadAPI.deleteDaemonSet(resourceName)
      } else if (resourceType === 'jobs') {
        await workloadAPI.deleteJob(resourceName)
      } else if (resourceType === 'cronjobs') {
        await workloadAPI.deleteCronJob(resourceName)
      } else if (resourceType === 'configmaps') {
        await configAPI.deleteConfigMap(resourceName)
      } else if (resourceType === 'secrets') {
        await configAPI.deleteSecret(resourceName)
      } else if (resourceType === 'services') {
        await networkAPI.deleteService(resourceName)
      } else if (resourceType === 'ingresses') {
        await networkAPI.deleteIngress(resourceName)
      } else if (resourceType === 'pvcs') {
        await storageAPI.deletePersistentVolumeClaim(resourceName)
      } else if (resourceType === 'pvs') {
        await storageAPI.deletePersistentVolume(resourceName)
      } else if (resourceType === 'serviceaccounts') {
        await configAPI.deleteServiceAccount(resourceName)
      } else if (resourceType === 'crds') {
        await crdAPI.deleteCRD(resourceName)
      } else if (resourceType === 'custom_resource' && crdMeta) {
        const isClusterScoped = crdMeta.scope === 'Cluster'
        let version = 'v1'
        if (Array.isArray(crdMeta.versions) && crdMeta.versions.length > 0) {
          const first = crdMeta.versions[0]
          if (typeof first === 'string') {
            version = first
          } else if (typeof first === 'object' && first !== null) {
            version = crdMeta.versions.find(v => v.storage)?.name || first.name || 'v1'
          }
        }
        if (isClusterScoped) {
          await crdAPI.deleteClusterCustomResource(crdMeta.group, version, crdMeta.plural, resourceName)
        } else {
          await crdAPI.deleteCustomResource(crdMeta.group, version, crdMeta.plural, resourceName)
        }
      } else {
        await v1API.deleteResource(resourceType, resourceName)
      }
      
      refetchResources()
    } catch (err) {
      console.error('Error deleting:', err)
      throw err
    }
  }

  // Map resource type to create type
  const getCreateType = () => {
    const mapping = {
      pods: 'pod',
      deployments: 'deployment',
      statefulsets: 'statefulset',
      daemonsets: 'daemonset',
      jobs: 'job',
      cronjobs: 'cronjob',
      configmaps: 'configmap',
      secrets: 'secret',
      services: 'service',
      ingresses: 'ingress',
      pvcs: 'pvc',
      quotas: 'quota',
      limitranges: 'limitrange',
      networkpolicies: 'networkpolicy',
      hpas: 'hpa',
    }
    return mapping[resourceType] || resourceType
  }

  const [showCreate, setShowCreate] = useState(false)

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">No Cluster Selected</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  // Show loading state while fetching CRD metadata
  if (isCustomResourceInstance && crdMetaLoading) {
    return (
      <div className="glass-card p-6">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-500"></div>
          <p className="text-slate-400">Loading CRD metadata...</p>
        </div>
      </div>
    )
  }

  // Display namespace - show "All" instead of "_all"
  const displayNamespace = activeNamespace === '_all' ? 'All' : activeNamespace

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{title}</h1>
          <p className="text-slate-400 mt-2">
            {isCustomResourceInstance && crdMeta ? (
              <>
                Group: <span className="font-semibold text-cyan-400">{crdMeta.group}</span>
                {' | '}Scope: <span className="font-semibold text-cyan-400">{crdMeta.scope}</span>
                {crdMeta.scope !== 'Cluster' && (
                  <>{' | '}Namespace: <span className="font-semibold text-cyan-400">{displayNamespace}</span></>
                )}
              </>
            ) : (
              <>Namespace: <span className="font-semibold text-cyan-400">{displayNamespace}</span></>
            )}
          </p>
        </div>
        {resourceType !== 'crds' && resourceType !== 'custom_resource' && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 transition-all"
          >
            <PlusIcon className="h-5 w-5" />
            Create
          </button>
        )}
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

      <DetailOverlay
        isOpen={showDetail}
        title={selectedResource?.name}
        data={detailData}
        loading={detailLoading}
        resourceType={resourceType}
        onScale={handleScale}
        onSave={handleSave}
        onDelete={handleDelete}
        onClose={() => setShowDetail(false)}
        fetchYaml={resourceType === 'custom_resource' || resourceType === 'crds' ? null : (resourceType, name) => v1API.getResourceYaml(resourceType, name)}
        applyYaml={resourceType === 'custom_resource' || resourceType === 'crds' ? null : (resourceType, name, yaml, dryRun) => v1API.applyResourceYaml(resourceType, name, yaml, dryRun)}
      />

      <CreateResource
        isOpen={showCreate}
        resourceType={getCreateType()}
        onClose={() => setShowCreate(false)}
        onSuccess={() => { setShowCreate(false); refetchResources(); }}
      />
    </div>
  )
}
