/**
 * API Client for Kubernetes Control Plane
 * Handles all HTTP requests to the backend with error handling and auth
 */

import axios from 'axios'

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: '',
  withCredentials: true, // Include cookies in requests
})

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Handle unauthorized - redirect to login
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
export { apiClient }

// ============================================================================
// V1 API CALLS (Clusters, Context, Namespaces)
// ============================================================================

export const v1API = {
  listClusters: () => apiClient.get('/v1/clusters'),
  addCluster: (data) => apiClient.post('/v1/clusters', data),
  getContext: () => apiClient.get('/v1/context'),
  setCluster: (clusterId) => apiClient.post('/v1/context/cluster', { cluster_id: clusterId }),
  setNamespace: (namespace) => apiClient.post('/v1/context/namespace', { namespace }),
  listNamespaces: () => apiClient.get('/v1/namespaces'),
  getNamespaceDetails: (namespaceName) => apiClient.get(`/v1/namespaces/${namespaceName}`),
  getNamespaceEvents: (namespaceName) => apiClient.get(`/v1/namespaces/${namespaceName}/events`),
  applyResource: (resourceType, name, yaml) => apiClient.post(`/v1/resources/${resourceType}/${name}/apply`, { yaml }),
  getResourceYaml: (resourceType, name) => apiClient.get(`/api/resources/${resourceType}/${name}/yaml`),
  applyResourceYaml: (resourceType, name, yaml, dryRun = false) => apiClient.put(`/api/resources/${resourceType}/${name}/yaml`, { yaml, dry_run: dryRun }),
  deleteResource: (resourceType, name) => apiClient.delete(`/api/resources/${resourceType}/${name}`),
  
  // RBAC Detail endpoints
  getRole: (name) => apiClient.get(`/api/resources/roles/${name}`),
  getRoleBinding: (name) => apiClient.get(`/api/resources/rolebindings/${name}`),
  getClusterRole: (name) => apiClient.get(`/api/resources/clusterroles/${name}`),
  getClusterRoleBinding: (name) => apiClient.get(`/api/resources/clusterrolebindings/${name}`),
  getEndpoints: (name) => apiClient.get(`/api/resources/endpoints/${name}`),
}

// ============================================================================
// METRICS API CALLS
// ============================================================================

export const metricsAPI = {
  getClusterMetrics: () => apiClient.get('/api/metrics/cluster'),
  getNodeMetrics: () => apiClient.get('/api/metrics/nodes'),
  getNodeMetric: (nodeName) => apiClient.get(`/api/metrics/nodes/${nodeName}`),
  getNamespaceMetrics: (namespace) => apiClient.get(`/api/metrics/namespace/${namespace}`),
  getPodMetrics: (namespace, podName) => apiClient.get(`/api/metrics/pod/${namespace}/${podName}`),
  getPVCMetrics: (namespace) => apiClient.get(`/api/metrics/pvc/${namespace}`),
  getMetricsHealth: () => apiClient.get('/api/metrics/health'),
  debugNodeMetrics: () => apiClient.get('/api/metrics/debug/nodes'),
}

// ============================================================================
// WORKLOAD API CALLS
// ============================================================================

export const workloadAPI = {
  // Pods
  listPods: () => apiClient.get('/api/resources/workload/pods'),
  getPod: (podName) => apiClient.get(`/api/resources/workload/pods/${podName}`),
  getPodLogs: (podName, container) => apiClient.get(`/api/resources/workload/pods/${podName}/logs`, { params: { container } }),
  deletePod: (podName) => apiClient.delete(`/api/resources/workload/pods/${podName}`),

  // Deployments
  listDeployments: () => apiClient.get('/api/resources/workload/deployments'),
  getDeployment: (name) => apiClient.get(`/api/resources/workload/deployments/${name}`),
  scaleDeployment: (name, replicas) => apiClient.patch(`/api/resources/workload/deployments/${name}/scale`, { replicas }),
  updateDeploymentImage: (name, containerIndex, image) => apiClient.patch(`/api/resources/workload/deployments/${name}/update-image`, { containerIndex, image }),
  rolloutDeployment: (name, action) => apiClient.patch(`/api/resources/workload/deployments/${name}/rollout`, { action }),
  deleteDeployment: (name) => apiClient.delete(`/api/resources/workload/deployments/${name}`),

  // ReplicaSets
  listReplicaSets: () => apiClient.get('/api/resources/workload/replicasets'),
  getReplicaSet: (name) => apiClient.get(`/api/resources/workload/replicasets/${name}`),

  // StatefulSets
  listStatefulSets: () => apiClient.get('/api/resources/workload/statefulsets'),
  getStatefulSet: (name) => apiClient.get(`/api/resources/workload/statefulsets/${name}`),
  scaleStatefulSet: (name, replicas) => apiClient.patch(`/api/resources/workload/statefulsets/${name}/scale`, { replicas }),
  deleteStatefulSet: (name) => apiClient.delete(`/api/resources/workload/statefulsets/${name}`),

  // DaemonSets
  listDaemonSets: () => apiClient.get('/api/resources/workload/daemonsets'),
  getDaemonSet: (name) => apiClient.get(`/api/resources/workload/daemonsets/${name}`),
  deleteDaemonSet: (name) => apiClient.delete(`/api/resources/workload/daemonsets/${name}`),

  // Jobs
  listJobs: () => apiClient.get('/api/resources/workload/jobs'),
  getJob: (name) => apiClient.get(`/api/resources/workload/jobs/${name}`),
  deleteJob: (name) => apiClient.delete(`/api/resources/workload/jobs/${name}`),

  // CronJobs
  listCronJobs: () => apiClient.get('/api/resources/workload/cronjobs'),
  getCronJob: (name) => apiClient.get(`/api/resources/workload/cronjobs/${name}`),
  deleteCronJob: (name) => apiClient.delete(`/api/resources/workload/cronjobs/${name}`),
}

// ============================================================================
// CONFIG API CALLS
// ============================================================================

export const configAPI = {
  // ConfigMaps
  listConfigMaps: () => apiClient.get('/api/resources/config/configmaps'),
  getConfigMap: (name) => apiClient.get(`/api/resources/config/configmaps/${name}`),
  editConfigMap: (name, data) => apiClient.put(`/api/resources/config/configmaps/${name}`, data),
  deleteConfigMap: (name) => apiClient.delete(`/api/resources/config/configmaps/${name}`),

  // Secrets
  listSecrets: () => apiClient.get('/api/resources/config/secrets'),
  getSecret: (name) => apiClient.get(`/api/resources/config/secrets/${name}`),
  editSecret: (name, data) => apiClient.put(`/api/resources/config/secrets/${name}`, data),
  deleteSecret: (name) => apiClient.delete(`/api/resources/config/secrets/${name}`),

  // HPAs
  listHPAs: () => apiClient.get('/api/resources/config/hpas'),
  getHPA: (name) => apiClient.get(`/api/resources/config/hpas/${name}`),
  editHPA: (name, spec) => apiClient.put(`/api/resources/config/hpas/${name}`, { spec }),

  // Resource Quotas
  listResourceQuotas: () => apiClient.get('/api/resources/config/quotas'),
  getResourceQuota: (name) => apiClient.get(`/api/resources/config/quotas/${name}`),

  // Limit Ranges
  listLimitRanges: () => apiClient.get('/api/resources/config/limitranges'),
  getLimitRange: (name) => apiClient.get(`/api/resources/config/limitranges/${name}`),

  // Service Accounts
  listServiceAccounts: () => apiClient.get('/api/resources/config/serviceaccounts'),
  getServiceAccount: (name) => apiClient.get(`/api/resources/config/serviceaccounts/${name}`),
  deleteServiceAccount: (name) => apiClient.delete(`/api/resources/config/serviceaccounts/${name}`),
}

// ============================================================================
// NETWORK API CALLS
// ============================================================================

export const networkAPI = {
  // Services
  listServices: () => apiClient.get('/api/resources/network/services'),
  getService: (name) => apiClient.get(`/api/resources/network/services/${name}`),
  deleteService: (name) => apiClient.delete(`/api/resources/network/services/${name}`),

  // Endpoints
  listEndpoints: () => apiClient.get('/api/resources/network/endpoints'),
  getEndpoints: (name) => apiClient.get(`/api/resources/network/endpoints/${name}`),

  // Ingresses
  listIngresses: () => apiClient.get('/api/resources/network/ingresses'),
  getIngress: (name) => apiClient.get(`/api/resources/network/ingresses/${name}`),
  deleteIngress: (name) => apiClient.delete(`/api/resources/network/ingresses/${name}`),

  // NetworkPolicies
  listNetworkPolicies: () => apiClient.get('/api/resources/network/networkpolicies'),
  getNetworkPolicy: (name) => apiClient.get(`/api/resources/network/networkpolicies/${name}`),
}

// ============================================================================
// STORAGE API CALLS
// ============================================================================

export const storageAPI = {
  // PersistentVolumes
  listPersistentVolumes: () => apiClient.get('/api/resources/storage/persistentvolumes'),
  getPersistentVolume: (name) => apiClient.get(`/api/resources/storage/persistentvolumes/${name}`),
  deletePersistentVolume: (name) => apiClient.delete(`/api/resources/storage/persistentvolumes/${name}`),

  // PersistentVolumeClaims
  listPersistentVolumeClaims: () => apiClient.get('/api/resources/storage/persistentvolumeclaims'),
  getPersistentVolumeClaim: (name) => apiClient.get(`/api/resources/storage/persistentvolumeclaims/${name}`),
  deletePersistentVolumeClaim: (name) => apiClient.delete(`/api/resources/storage/persistentvolumeclaims/${name}`),

  // StorageClasses
  listStorageClasses: () => apiClient.get('/api/resources/storage/storageclasses'),
  getStorageClass: (name) => apiClient.get(`/api/resources/storage/storageclasses/${name}`),
}

// ============================================================================
// CRD API CALLS
// ============================================================================

export const crdAPI = {
  // CRD Discovery
  listCRDs: () => apiClient.get('/api/resources/crds'),
  getCRD: (name) => apiClient.get(`/api/resources/crds/${name}`),
  deleteCRD: (name) => apiClient.delete(`/api/resources/crds/${name}`),

  // Namespaced Custom Resources
  listCustomResources: (group, version, plural) =>
    apiClient.get(`/api/resources/custom/${group}/${version}/${plural}`),
  getCustomResource: (group, version, plural, name) =>
    apiClient.get(`/api/resources/custom/${group}/${version}/${plural}/${name}`),
  deleteCustomResource: (group, version, plural, name) =>
    apiClient.delete(`/api/resources/custom/${group}/${version}/${plural}/${name}`),

  // Cluster-scoped Custom Resources
  listClusterCustomResources: (group, version, plural) =>
    apiClient.get(`/api/resources/custom-cluster/${group}/${version}/${plural}`),
  getClusterCustomResource: (group, version, plural, name) =>
    apiClient.get(`/api/resources/custom-cluster/${group}/${version}/${plural}/${name}`),
  deleteClusterCustomResource: (group, version, plural, name) =>
    apiClient.delete(`/api/resources/custom-cluster/${group}/${version}/${plural}/${name}`),
}

// ============================================================================
// AUTH API CALLS
// ============================================================================

export const authAPI = {
  login: (email, password) => apiClient.post('/api/auth/login', { email, password }),
  register: (email, password, name) => apiClient.post('/api/auth/register', { email, password, name }),
  logout: () => apiClient.post('/api/auth/logout'),
  me: () => apiClient.get('/api/auth/me'),
}

// ============================================================================
// NODES API CALLS
// ============================================================================

export const nodesAPI = {
  listNodes: () => apiClient.get('/api/resources/nodes'),
  getNode: (nodeName) => apiClient.get(`/api/resources/nodes/${nodeName}`),
  cordonNode: (nodeName) => apiClient.post(`/api/resources/nodes/${nodeName}/cordon`),
  uncordonNode: (nodeName) => apiClient.post(`/api/resources/nodes/${nodeName}/uncordon`),
  drainNode: (nodeName) => apiClient.post(`/api/resources/nodes/${nodeName}/drain`),
}

// ============================================================================
// NAMESPACE REQUESTS API CALLS
// ============================================================================

export const namespaceRequestsAPI = {
  list: () => apiClient.get('/api/namespace-requests'),
  create: (data) => apiClient.post('/api/namespace-requests', data),
  approve: (id, action, comment) => apiClient.post(`/api/namespace-requests/${id}/approve`, { action, comment }),
  delete: (id) => apiClient.delete(`/api/namespace-requests/${id}`),
}

// ============================================================================
// SECURITY API CALLS
// ============================================================================

export const securityAPI = {
  scan: () => apiClient.get('/api/security/scan'),
}

// ============================================================================
// HISTORY API CALLS
// ============================================================================

export const historyAPI = {
  list: (params) => apiClient.get('/api/history', { params }),
  getTypes: () => apiClient.get('/api/history/types'),
  getEntry: (id) => apiClient.get(`/api/history/${id}`),
  getDiff: (id, params) => apiClient.get(`/api/history/${id}/diff`, { params }),
  restore: (id) => apiClient.post(`/api/history/${id}/restore`),
}

// ============================================================================
// COST ANALYSIS API CALLS
// ============================================================================

export const costAPI = {
  analyze: () => apiClient.get('/api/cost/analyze'),
  rightsize: () => apiClient.get('/api/cost/rightsize'),
}
