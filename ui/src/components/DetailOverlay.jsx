/**
 * DetailOverlay Component
 * Modal for viewing and editing resource details with tabs
 */

import React, { useState, useEffect } from 'react'
import { XMarkIcon, PencilIcon, ArrowPathIcon, CheckIcon, PlusIcon, TrashIcon, ArrowDownTrayIcon, CommandLineIcon } from '@heroicons/react/24/outline'
import yaml from 'js-yaml'
import { v1API, workloadAPI } from '../api'
import PodTerminal from './PodTerminal'

export default function DetailOverlay({
  isOpen = false,
  title = '',
  data = null,
  loading = false,
  resourceType = '',
  onClose = null,
  onSave = null,
  onScale = null,
  onDelete = null,
  customContent = null,
  customTabs = null,
  events = [],
  fetchYaml = null,
  applyYaml = null,
}) {
  const [activeTab, setActiveTab] = useState('overview')
  const [editMode, setEditMode] = useState(false)
  const [editedData, setEditedData] = useState({})
  const [saving, setSaving] = useState(false)
  const [scaleReplicas, setScaleReplicas] = useState(0)
  const [yamlContent, setYamlContent] = useState('')
  const [yamlError, setYamlError] = useState(null)
  const [configMapData, setConfigMapData] = useState({})
  const [secretData, setSecretData] = useState({})
  
  // Pod logs state
  const [podLogs, setPodLogs] = useState('')
  const [logsLoading, setLogsLoading] = useState(false)
  const [selectedContainer, setSelectedContainer] = useState('')
  const [containers, setContainers] = useState([])
  
  // Notifications
  const [notification, setNotification] = useState(null)
  const [fullYaml, setFullYaml] = useState('')
  const [yamlLoading, setYamlLoading] = useState(false)
  
  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (isOpen && title && resourceType && fetchYaml) {
      setYamlLoading(true)
      fetchYaml(resourceType, title)
        .then(res => {
          setFullYaml(res.data.yaml || '')
          setYamlContent(res.data.yaml || '')
        })
        .catch(err => {
          console.error('Error fetching full YAML:', err)
          // Fall back to data-based YAML
          try {
            const fallbackYaml = yaml.dump(data, { indent: 2, lineWidth: -1 })
            setFullYaml(fallbackYaml)
            setYamlContent(fallbackYaml)
          } catch (e) {
            setFullYaml(JSON.stringify(data, null, 2))
            setYamlContent(JSON.stringify(data, null, 2))
          }
        })
        .finally(() => setYamlLoading(false))
    }
  }, [isOpen, title, resourceType])

  // Reset container selection when pod changes
  useEffect(() => {
    setSelectedContainer('')
    setContainers([])
  }, [title, isOpen])

  useEffect(() => {
    if (data) {
      setEditedData(data)
      if (data.spec?.replicas !== undefined) {
        setScaleReplicas(data.spec.replicas)
      }
      if (data.data) {
        setConfigMapData({ ...data.data })
      }
      if (data.data && resourceType === 'secrets') {
        setSecretData({ ...data.data })
      }
      if (data.spec?.containers) {
        setContainers(data.spec.containers.map(c => c.name))
        if (data.spec.containers.length > 0 && !selectedContainer) {
          setSelectedContainer(data.spec.containers[0].name)
        }
      } else if (data.containers) {
        const containerNames = data.containers.map(c => c.name || c)
        setContainers(containerNames)
        if (containerNames.length > 0 && !selectedContainer) {
          setSelectedContainer(containerNames[0])
        }
      }
      try {
        setYamlContent(yaml.dump(data, { indent: 2, lineWidth: -1 }))
      } catch (e) {
        setYamlContent(JSON.stringify(data, null, 2))
      }
    }
  }, [data])

  // Fetch logs when pod tab is selected
  useEffect(() => {
    if (activeTab === 'logs' && title && selectedContainer && resourceType === 'pods') {
      fetchPodLogs()
    }
  }, [activeTab, title, selectedContainer, resourceType])

  const fetchPodLogs = async () => {
    setLogsLoading(true)
    try {
      const response = await workloadAPI.getPodLogs(title, selectedContainer)
      setPodLogs(response.data.logs || '')
    } catch (err) {
      console.error('Error fetching logs:', err)
      setPodLogs('Error fetching logs: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLogsLoading(false)
    }
  }

  const downloadLogs = () => {
    const blob = new Blob([podLogs], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title}-${selectedContainer}.log`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 3000)
  }

  const handleDelete = async () => {
    if (!onDelete) return
    
    setDeleting(true)
    try {
      await onDelete(title)
      showNotification(`${resourceType.slice(0, -1)} "${title}" deleted successfully`, 'success')
      setShowDeleteConfirm(false)
      if (onClose) onClose()
    } catch (err) {
      showNotification('Failed to delete: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setDeleting(false)
    }
  }

  const getResourceTabs = () => {
    const defaultTabs = [
      { id: 'overview', label: 'Overview' },
      { id: 'yaml', label: 'YAML' },
      { id: 'metadata', label: 'Metadata' },
      { id: 'spec', label: 'Spec' },
      { id: 'status', label: 'Status' },
    ]

    const crdTabs = [
      { id: 'overview', label: 'Overview' },
      { id: 'yaml', label: 'YAML' },
    ]

    const rbacTabs = {
      roles: [
        { id: 'overview', label: 'Overview' },
        { id: 'rules', label: 'Rules' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
      clusterroles: [
        { id: 'overview', label: 'Overview' },
        { id: 'rules', label: 'Rules' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
      rolebindings: [
        { id: 'overview', label: 'Overview' },
        { id: 'subjects', label: 'Subjects' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
      clusterrolebindings: [
        { id: 'overview', label: 'Overview' },
        { id: 'subjects', label: 'Subjects' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
    }

    const networkTabs = {
      services: [
        { id: 'overview', label: 'Overview' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
      ingresses: [
        { id: 'overview', label: 'Overview' },
        { id: 'rules', label: 'Rules' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
      endpoints: [
        { id: 'overview', label: 'Overview' },
        { id: 'yaml', label: 'YAML' },
        { id: 'metadata', label: 'Metadata' },
      ],
    }

    if (resourceType === 'pods') {
      return [...defaultTabs.slice(0, 1), { id: 'logs', label: 'Logs' }, { id: 'terminal', label: 'Terminal' }, ...defaultTabs.slice(1)]
    }

    if (resourceType === 'crds') {
      return crdTabs
    }

    return rbacTabs[resourceType] || networkTabs[resourceType] || customTabs || defaultTabs
  }

  const tabs = getResourceTabs()

  if (!isOpen) return null

  const getEditableFields = () => {
    const editable = []
    if ((resourceType === 'deployments' || resourceType === 'statefulsets') && data?.spec?.replicas !== undefined) {
      editable.push({
        key: 'replicas',
        label: 'Replicas',
        current: data.spec.replicas,
        type: 'number'
      })
      if (data.spec?.template?.spec?.containers) {
        data.spec.template.spec.containers.forEach((container, idx) => {
          editable.push({
            key: `image-${idx}`,
            label: `Container ${idx + 1} Image`,
            current: container.image || '',
            type: 'text',
            containerIndex: idx,
            containerName: container.name
          })
        })
      }
    }
    return editable
  }

  const handleScale = async () => {
    if (onScale && scaleReplicas !== data?.spec?.replicas) {
      setSaving(true)
      showNotification('Scale up/down triggered...', 'info')
      try {
        await onScale(title, scaleReplicas)
        showNotification(`Successfully scaled to ${scaleReplicas} replicas`, 'success')
      } catch (err) {
        showNotification('Failed to scale: ' + (err.response?.data?.detail || err.message), 'error')
      } finally {
        setSaving(false)
      }
    }
  }

  const handleImageUpdate = async (containerIndex, newImage) => {
    if (!data || !onScale) return
    
    setSaving(true)
    showNotification('Image update triggered...', 'info')
    try {
      await onScale(title, data.spec.replicas, containerIndex, newImage)
      showNotification(`Successfully updated container image`, 'success')
    } catch (err) {
      showNotification('Failed to update image: ' + (err.response?.data?.detail || err.message), 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleYamlSave = async () => {
    if (!applyYaml && !onSave) return
    
    setSaving(true)
    setYamlError(null)
    try {
      const parsed = yaml.load(yamlContent)
      
      if (!parsed || typeof parsed !== 'object') {
        throw new Error('Invalid YAML format')
      }
      
      const resourceName = title || parsed?.metadata?.name
      
      // If applyYaml is provided (new server-side apply), use it for all resources
      if (applyYaml) {
        const yamlToApply = yaml.dump(parsed, { lineWidth: -1 })
        await applyYaml(resourceType, resourceName, yamlToApply)
        showNotification('Changes applied successfully', 'success')
        setEditMode(false)
        
        // Refresh the YAML to show the actual state after apply
        if (fetchYaml) {
          const res = await fetchYaml(resourceType, resourceName)
          setFullYaml(res.data.yaml || '')
          setYamlContent(res.data.yaml || '')
        }
        setSaving(false)
        return
      }
      
      // Legacy code path - for resources that don't have applyYaml
      // For deployments - detect specific changes
      if (resourceType === 'deployments') {
        const currentData = data || {}
        
        // Check if ONLY replicas changed - use scale API
        const replicasChanged = parsed.spec?.replicas !== undefined && 
          parsed.spec.replicas !== (currentData.spec?.replicas || currentData.replicas)
        
        // Check if ONLY images changed - use image update API
        let imagesChanged = false
        if (parsed.spec?.template?.spec?.containers) {
          for (let i = 0; i < parsed.spec.template.spec.containers.length; i++) {
            const newContainer = parsed.spec.template.spec.containers[i]
            const currentContainer = currentData.spec?.template?.spec?.containers?.[i] || currentData.containers?.[i]
            if (currentContainer && newContainer.image !== currentContainer.image) {
              imagesChanged = true
              break
            }
          }
        }
        
        // If only replicas changed, use scale API
        if (replicasChanged && !imagesChanged) {
          await workloadAPI.scaleDeployment(resourceName, parsed.spec.replicas)
          showNotification('Replica count updated successfully', 'success')
          setEditMode(false)
          setSaving(false)
          // Refresh the detail data
          if (onScale) onScale(resourceName, parsed.spec.replicas)
          return
        }
        
        // If only images changed, use image update API
        if (imagesChanged && !replicasChanged) {
          const updates = []
          for (let i = 0; i < parsed.spec.template.spec.containers.length; i++) {
            const newContainer = parsed.spec.template.spec.containers[i]
            const currentContainer = currentData.spec?.template?.spec?.containers?.[i] || currentData.containers?.[i]
            if (currentContainer && newContainer.image !== currentContainer.image) {
              updates.push({ index: i, image: newContainer.image, name: newContainer.name })
            }
          }
          for (const update of updates) {
            await workloadAPI.updateDeploymentImage(resourceName, update.index, update.image)
          }
          showNotification(`Updated ${updates.length} container image(s)`, 'success')
          setEditMode(false)
          setSaving(false)
          return
        }
        
        // For all other changes (or both replicas and images), use apply with full YAML
        const applyYamlStr = yaml.dump(parsed, { lineWidth: -1 })
        await v1API.applyResource(resourceType, resourceName, applyYamlStr)
        showNotification('Changes applied successfully', 'success')
        setEditMode(false)
        setSaving(false)
        return
      }
      
      // For statefulsets - use scale API for replicas
      if (resourceType === 'statefulsets') {
        const currentData = data || {}
        if (parsed.spec?.replicas !== undefined && parsed.spec.replicas !== currentData.spec?.replicas) {
          await workloadAPI.scaleStatefulSet(resourceName, parsed.spec.replicas)
          showNotification('Replica count updated successfully', 'success')
          setEditMode(false)
          setSaving(false)
          return
        }
        // For other changes, use apply
        const applyYamlStr = yaml.dump(parsed, { lineWidth: -1 })
        await v1API.applyResource(resourceType, resourceName, applyYamlStr)
        showNotification('Changes applied successfully', 'success')
        setEditMode(false)
        setSaving(false)
        return
      }
      
      // For configmaps/secrets - allow updating data
      if (resourceType === 'configmaps' || resourceType === 'secrets') {
        if (parsed.data) {
          await onSave(resourceName, { data: parsed.data })
          showNotification('Changes applied successfully', 'success')
          setEditMode(false)
          setSaving(false)
          return
        }
      }
      
      // For other resources - sanitize and apply
      let patch = { ...parsed }
      if (patch.status) delete patch.status
      if (patch.metadata) {
        delete patch.metadata.resourceVersion
        delete patch.metadata.uid
        delete patch.metadata.creationTimestamp
        delete patch.metadata.managedFields
      }
      
      const patchYaml = yaml.dump(patch, { lineWidth: -1 })
      await v1API.applyResource(resourceType, resourceName, patchYaml)
      setEditMode(false)
      showNotification('Changes applied successfully', 'success')
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to apply changes'
      setYamlError(errorMsg)
      showNotification('Failed to apply changes: ' + errorMsg, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleConfigMapChange = (key, value) => {
    setConfigMapData(prev => ({ ...prev, [key]: value }))
  }

  const handleConfigMapSave = async () => {
    if (!onSave) return
    setSaving(true)
    try {
      await onSave(title, { data: configMapData })
      showNotification('ConfigMap saved successfully', 'success')
    } catch (err) {
      showNotification('Error saving ConfigMap: ' + err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleSecretChange = (key, value) => {
    setSecretData(prev => ({ ...prev, [key]: value }))
  }

  const handleSecretSave = async () => {
    if (!onSave) return
    setSaving(true)
    try {
      await onSave(title, { data: secretData })
      showNotification('Secret saved successfully', 'success')
    } catch (err) {
      showNotification('Error saving Secret: ' + err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const addConfigMapKey = () => {
    const key = `key-${Object.keys(configMapData).length + 1}`
    setConfigMapData(prev => ({ ...prev, [key]: '' }))
  }

  const removeConfigMapKey = (key) => {
    const newData = { ...configMapData }
    delete newData[key]
    setConfigMapData(newData)
  }

  const addSecretKey = () => {
    const key = `key-${Object.keys(secretData).length + 1}`
    setSecretData(prev => ({ ...prev, [key]: '' }))
  }

  const removeSecretKey = (key) => {
    const newData = { ...secretData }
    delete newData[key]
    setSecretData(newData)
  }

  const renderOverview = () => {
    if (customContent) return customContent
    if (!data) return null

    // CRD-specific overview
    if (resourceType === 'crds') {
      return (
        <div className="space-y-6">
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">CRD Information</h4>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-slate-400">Name</dt>
                <dd className="text-sm font-medium text-white">{data.name || title}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Group</dt>
                <dd className="text-sm font-medium text-cyan-400">{data.group || '-'}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Kind</dt>
                <dd className="text-sm font-medium text-white">{data.kind || '-'}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Scope</dt>
                <dd className="text-sm font-medium text-white">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    data.scope === 'Cluster'
                      ? 'bg-purple-600/20 text-purple-400 border border-purple-500/30'
                      : 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                  }`}>
                    {data.scope || '-'}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Plural</dt>
                <dd className="text-sm font-mono text-white">{data.plural || '-'}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Singular</dt>
                <dd className="text-sm font-mono text-white">{data.singular || '-'}</dd>
              </div>
              {data.created && (
                <div>
                  <dt className="text-xs text-slate-400">Created</dt>
                  <dd className="text-sm font-medium text-white">{data.created}</dd>
                </div>
              )}
            </dl>
          </div>

          {data.versions && data.versions.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-white mb-3">Versions</h4>
              <div className="space-y-2">
                {data.versions.map((ver, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                    <span className="text-sm font-mono text-white">{typeof ver === 'object' ? ver.name : ver}</span>
                    {typeof ver === 'object' && ver.storage && (
                      <span className="px-2 py-0.5 bg-green-600/20 text-green-400 text-xs rounded border border-green-500/30">Storage</span>
                    )}
                    {typeof ver === 'object' && ver.served && (
                      <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 text-xs rounded border border-blue-500/30">Served</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.labels && Object.keys(data.labels).length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-white mb-3">Labels</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.labels).map(([key, value]) => (
                  <span key={key} className="inline-flex items-center px-2 py-1 rounded bg-blue-600/20 text-xs text-cyan-400 border border-blue-500/30">
                    {key}: {value}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.annotations && Object.keys(data.annotations).length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-white mb-3">Annotations</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.annotations).map(([key, value]) => (
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

    const statusInfo = []
    
    if (data.status) {
      if (data.status.phase) statusInfo.push({ label: 'Phase', value: data.status.phase })
      if (data.status.podIP) statusInfo.push({ label: 'Pod IP', value: data.status.podIP })
      if (data.status.hostIP) statusInfo.push({ label: 'Host IP', value: data.status.hostIP })
      if (data.status.startTime) statusInfo.push({ label: 'Started', value: data.status.startTime })
      if (data.status.replicas !== undefined) statusInfo.push({ label: 'Replicas', value: `${data.status.replicas} desired` })
      if (data.status.readyReplicas !== undefined) statusInfo.push({ label: 'Ready', value: `${data.status.readyReplicas}/${data.status.replicas || 0}` })
      if (data.status.availableReplicas !== undefined) statusInfo.push({ label: 'Available', value: data.status.availableReplicas })
      if (data.status.updatedReplicas !== undefined) statusInfo.push({ label: 'Updated', value: data.status.updatedReplicas })
      if (data.status.desiredNumberScheduled !== undefined) statusInfo.push({ label: 'Desired', value: data.status.desiredNumberScheduled })
      if (data.status.numberReady !== undefined) statusInfo.push({ label: 'Ready', value: data.status.numberReady })
    }

    const isIngress = resourceType === 'ingresses' || data.kind === 'Ingress'
    const isService = resourceType === 'services' || data.kind === 'Service'
    const isRole = resourceType === 'roles' || data.kind === 'Role' || data.kind === 'ClusterRole'
    const isRoleBinding = resourceType === 'rolebindings' || data.kind === 'RoleBinding' || data.kind === 'ClusterRoleBinding'
    const isEndpoints = resourceType === 'endpoints' || data.kind === 'Endpoints'

    return (
      <div className="space-y-6">
        <div>
          <h4 className="text-sm font-semibold text-white mb-3">Basic Information</h4>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-xs text-slate-400">Name</dt>
              <dd className="text-sm font-medium text-white">{data.metadata?.name || title}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Namespace</dt>
              <dd className="text-sm font-medium text-white">{data.metadata?.namespace || '-'}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Kind</dt>
              <dd className="text-sm font-medium text-white">{data.kind || '-'}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">APIVersion</dt>
              <dd className="text-sm font-medium text-white">{data.apiVersion || '-'}</dd>
            </div>
          </dl>
        </div>

        {isIngress && data.rules && data.rules.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Rules</h4>
            <div className="space-y-3">
              {data.rules.map((rule, idx) => (
                <div key={idx} className="border border-slate-700 rounded-lg p-3 bg-slate-800/30">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-slate-400">Host:</span>
                    <span className="text-sm font-medium text-cyan-400">{rule.host || '*'}</span>
                  </div>
                  {rule.paths && rule.paths.length > 0 && (
                    <div className="ml-2 space-y-2">
                      {rule.paths.map((path, pathIdx) => (
                        <div key={pathIdx} className="text-xs">
                          <span className="text-slate-400">Path: </span>
                          <span className="text-white font-mono">{path.path}</span>
                          <span className="text-slate-500"> ({path.path_type})</span>
                          <span className="text-slate-400 ml-2">→ {path.backend_service}:{path.backend_port}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {isIngress && data.tls && data.tls.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">TLS</h4>
            <div className="space-y-2">
              {data.tls.map((tls, idx) => (
                <div key={idx} className="border border-slate-700 rounded-lg p-3 bg-slate-800/30">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-green-400 font-medium">TLS Enabled</span>
                    {tls.secret_name && (
                      <span className="text-xs text-slate-400">Secret: {tls.secret_name}</span>
                    )}
                  </div>
                  {tls.hosts && tls.hosts.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {tls.hosts.map((host, hostIdx) => (
                        <span key={hostIdx} className="px-2 py-1 bg-green-600/20 text-green-400 text-xs rounded border border-green-500/30">
                          {host}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {isService && data.spec && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Service Spec</h4>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-slate-400">Type</dt>
                <dd className="text-sm font-medium text-white">{data.spec.type || '-'}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Cluster IP</dt>
                <dd className="text-sm font-mono text-white">{data.spec.clusterIP || '-'}</dd>
              </div>
              {data.spec.selector && Object.keys(data.spec.selector).length > 0 && (
                <div className="col-span-2">
                  <dt className="text-xs text-slate-400 mb-2">Selector</dt>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(data.spec.selector).map(([key, value]) => (
                      <span key={key} className="inline-flex items-center px-2 py-1 rounded bg-purple-600/20 text-xs text-purple-400 border border-purple-500/30">
                        {key}: {value}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {data.spec.ports && data.spec.ports.length > 0 && (
                <div className="col-span-2">
                  <dt className="text-xs text-slate-400 mb-2">Ports</dt>
                  <div className="space-y-2">
                    {data.spec.ports.map((port, idx) => (
                      <div key={idx} className="bg-slate-800/50 p-2 rounded border border-slate-700">
                        <span className="text-sm text-white font-mono">{port.name || `port-${idx}`}</span>
                        <span className="text-slate-400"> : </span>
                        <span className="text-sm text-cyan-400 font-mono">{port.port}</span>
                        <span className="text-slate-500"> → </span>
                        <span className="text-sm text-cyan-400 font-mono">{port.targetPort}</span>
                        <span className="text-slate-400 text-xs ml-2">({port.protocol})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </dl>
          </div>
        )}

        {data.metadata?.labels && Object.keys(data.metadata.labels).length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Labels</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.metadata.labels).map(([key, value]) => (
                <span key={key} className="inline-flex items-center px-2 py-1 rounded bg-blue-600/20 text-xs text-cyan-400 border border-blue-500/30">
                  {key}: {value}
                </span>
              ))}
            </div>
          </div>
        )}

        {data.metadata?.annotations && Object.keys(data.metadata.annotations).length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Annotations</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.metadata.annotations).map(([key, value]) => (
                <span key={key} className="inline-flex items-center px-2 py-1 rounded bg-slate-700/50 text-xs text-slate-300 border border-slate-600/50">
                  {key}: {value}
                </span>
              ))}
            </div>
          </div>
        )}

        {statusInfo.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Status</h4>
            <dl className="grid grid-cols-2 gap-4">
              {statusInfo.map((item, idx) => (
                <div key={idx}>
                  <dt className="text-xs text-slate-400">{item.label}</dt>
                  <dd className="text-sm font-medium text-white">{item.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {isRole && data.rules && data.rules.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Rules</h4>
            <div className="space-y-3">
              {data.rules.map((rule, idx) => (
                <div key={idx} className="border border-slate-700 rounded-lg p-3 bg-slate-800/30">
                  <div className="flex flex-wrap gap-1 mb-2">
                    {rule.verbs && rule.verbs.map((verb, vidx) => (
                      <span key={vidx} className="px-2 py-1 bg-purple-600/20 text-purple-400 text-xs rounded border border-purple-500/30">
                        {verb}
                      </span>
                    ))}
                  </div>
                  <div className="text-xs text-slate-400">
                    {rule.apiGroups && rule.apiGroups.length > 0 && (
                      <span className="mr-3">APIGroups: {rule.apiGroups.join(', ')}</span>
                    )}
                    {rule.resources && rule.resources.length > 0 && (
                      <span>Resources: {rule.resources.join(', ')}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {isRoleBinding && data.roleRef && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Role Ref</h4>
            <dl className="grid grid-cols-2 gap-4 bg-slate-800/30 p-3 rounded-lg border border-slate-700">
              <div>
                <dt className="text-xs text-slate-400">API Group</dt>
                <dd className="text-sm font-medium text-white">{data.roleRef.apiGroup || '-'}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">Kind</dt>
                <dd className="text-sm font-medium text-white">{data.roleRef.kind || '-'}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-slate-400">Name</dt>
                <dd className="text-sm font-mono text-cyan-400">{data.roleRef.name || '-'}</dd>
              </div>
            </dl>
          </div>
        )}

        {isRoleBinding && data.subjects && data.subjects.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Subjects</h4>
            <div className="space-y-2">
              {data.subjects.map((subject, idx) => (
                <div key={idx} className="border border-slate-700 rounded-lg p-3 bg-slate-800/30">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 text-xs rounded border border-blue-500/30">
                      {subject.kind}
                    </span>
                    <span className="text-sm font-medium text-white">{subject.name}</span>
                  </div>
                  <div className="text-xs text-slate-400">
                    {subject.namespace && <span className="mr-3">Namespace: {subject.namespace}</span>}
                    {subject.apiGroup && <span>APIGroup: {subject.apiGroup}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {isEndpoints && data.subsets && data.subsets.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold text-white mb-3">Endpoints Subsets</h4>
            <div className="space-y-4">
              {data.subsets.map((subset, idx) => (
                <div key={idx} className="border border-slate-700 rounded-lg p-4 bg-slate-800/30">
                  <h5 className="text-xs text-slate-400 mb-2">Addresses</h5>
                  <div className="space-y-2 mb-3">
                    {subset.addresses && subset.addresses.map((addr, aidx) => (
                      <div key={aidx} className="bg-slate-800/50 p-2 rounded border border-slate-700">
                        <span className="text-sm font-mono text-white">{addr.ip}</span>
                        {addr.hostname && <span className="text-xs text-slate-400 ml-2">({addr.hostname})</span>}
                        {addr.targetRef && addr.targetRef.name && (
                          <span className="text-xs text-cyan-400 ml-2">→ {addr.targetRef.kind}/{addr.targetRef.name}</span>
                        )}
                      </div>
                    ))}
                  </div>
                  {subset.ports && subset.ports.length > 0 && (
                    <div>
                      <h5 className="text-xs text-slate-400 mb-2">Ports</h5>
                      <div className="flex flex-wrap gap-2">
                        {subset.ports.map((port, pidx) => (
                          <span key={pidx} className="px-2 py-1 bg-green-600/20 text-green-400 text-xs rounded border border-green-500/30">
                            {port.name || port.port} : {port.port} ({port.protocol})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {getEditableFields().length > 0 && (
          <div className="border-t border-slate-700/50 pt-4">
            <h4 className="text-sm font-semibold text-white mb-3">Scale / Edit</h4>
            <div className="space-y-3">
              {getEditableFields().map((field, idx) => (
                <div key={idx} className="flex items-center gap-4">
                  <label className="text-sm text-slate-300 w-40">{field.label}:</label>
                  {field.type === 'number' ? (
                    <>
                      <input
                        type="number"
                        min="0"
                        value={field.key === 'replicas' ? scaleReplicas : field.current}
                        onChange={(e) => field.key === 'replicas' ? setScaleReplicas(parseInt(e.target.value) || 0) : null}
                        className="w-24 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                      />
                      {field.key === 'replicas' && (
                        <button
                          onClick={handleScale}
                          disabled={saving || scaleReplicas === data?.spec?.replicas}
                          className="px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded text-sm hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          <ArrowPathIcon className="h-4 w-4" />
                          {saving ? 'Updating...' : 'Update'}
                        </button>
                      )}
                    </>
                  ) : (
                    <div className="flex-1 flex items-center gap-2">
                      <input
                        type="text"
                        value={field.current}
                        readOnly
                        className="flex-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-300"
                      />
                      <button
                        onClick={() => {
                          const newImage = prompt('Enter new image:')
                          if (newImage && newImage !== field.current) {
                            handleImageUpdate(field.containerIndex, newImage)
                          }
                        }}
                        className="px-3 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-500"
                      >
                        Update
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {resourceType === 'configmaps' && data.data && (
          <div className="border-t border-slate-700/50 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-white">Data</h4>
              <button
                onClick={handleConfigMapSave}
                disabled={saving}
                className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-500 disabled:opacity-50 flex items-center gap-1"
              >
                <CheckIcon className="h-4 w-4" />
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
            <div className="space-y-2">
              {Object.entries(configMapData).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={key}
                    readOnly
                    className="w-40 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-300"
                  />
                  <span className="text-slate-500">=</span>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => handleConfigMapChange(key, e.target.value)}
                    className="flex-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                  <button
                    onClick={() => removeConfigMapKey(key)}
                    className="p-2 text-red-400 hover:bg-red-500/10 rounded"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <button
                onClick={addConfigMapKey}
                className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 text-sm"
              >
                <PlusIcon className="h-4 w-4" />
                Add Key
              </button>
            </div>
          </div>
        )}

        {resourceType === 'secrets' && data.data && (
          <div className="border-t border-slate-700/50 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-white">Data</h4>
              <button
                onClick={handleSecretSave}
                disabled={saving}
                className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-500 disabled:opacity-50 flex items-center gap-1"
              >
                <CheckIcon className="h-4 w-4" />
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
            <div className="space-y-2">
              {Object.keys(data.data).map((key) => (
                <div key={key} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={key}
                    readOnly
                    className="w-40 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-300"
                  />
                  <span className="text-slate-500">=</span>
                  <input
                    type="password"
                    value={secretData[key] || ''}
                    onChange={(e) => handleSecretChange(key, e.target.value)}
                    placeholder="Enter value"
                    className="flex-1 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {resourceType === 'serviceaccounts' && (
          <div className="border-t border-slate-700/50 pt-4">
            <h4 className="text-sm font-semibold text-white mb-3">Service Account Details</h4>
            
            {data.secrets && data.secrets.length > 0 && (
              <div className="mb-4">
                <h5 className="text-xs text-slate-400 mb-2">Secrets</h5>
                <div className="flex flex-wrap gap-2">
                  {data.secrets.map((secret, idx) => (
                    <span key={idx} className="inline-flex items-center px-2 py-1 rounded bg-purple-600/20 text-xs text-purple-400 border border-purple-500/30">
                      {typeof secret === 'object' ? secret.name : secret}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.imagePullSecrets && data.imagePullSecrets.length > 0 && (
              <div className="mb-4">
                <h5 className="text-xs text-slate-400 mb-2">Image Pull Secrets</h5>
                <div className="flex flex-wrap gap-2">
                  {data.imagePullSecrets.map((ips, idx) => (
                    <span key={idx} className="inline-flex items-center px-2 py-1 rounded bg-orange-600/20 text-xs text-orange-400 border border-orange-500/30">
                      {typeof ips === 'object' ? ips.name : ips}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.automountServiceAccountToken !== undefined && (
              <div className="mb-4">
                <h5 className="text-xs text-slate-400 mb-2">Automount Service Account Token</h5>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={data.automountServiceAccountToken}
                    readOnly
                    className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500"
                  />
                  <span className="text-sm text-slate-300">
                    {data.automountServiceAccountToken ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>
            )}

            {(!data.secrets || data.secrets.length === 0) && 
             (!data.imagePullSecrets || data.imagePullSecrets.length === 0) &&
             data.automountServiceAccountToken === undefined && (
              <p className="text-sm text-slate-500">No additional details</p>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderLogs = () => {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-slate-300">Container:</label>
            <select
              value={selectedContainer}
              onChange={(e) => setSelectedContainer(e.target.value)}
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            >
              {containers.map((container) => (
                <option key={container} value={container}>
                  {container}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={downloadLogs}
            disabled={!podLogs}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg text-sm hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50"
          >
            <ArrowDownTrayIcon className="h-4 w-4" />
            Download Logs
          </button>
        </div>
        
        {logsLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
          </div>
        ) : (
          <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg overflow-auto max-h-96 font-mono text-xs whitespace-pre-wrap border border-slate-700">
            {podLogs || 'No logs available'}
          </pre>
        )}
      </div>
    )
  }

  const renderYaml = () => {
    const displayYaml = yamlContent || fullYaml || (data ? yaml.dump(data, { indent: 2, lineWidth: -1 }) : '')
    
    return (
      <div className="relative">
        <div className="flex justify-end mb-2">
          {editMode ? (
            <div className="flex gap-2">
              <button
                onClick={() => { 
                  setEditMode(false); 
                  setYamlContent(fullYaml || displayYaml); 
                }}
                className="px-3 py-1 text-sm text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleYamlSave}
                disabled={saving}
                className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-500 disabled:opacity-50 flex items-center gap-1"
              >
                <CheckIcon className="h-4 w-4" />
                {saving ? 'Applying...' : 'Apply'}
              </button>
            </div>
          ) : (onSave || applyYaml) && (
            <button
              onClick={() => setEditMode(true)}
              className="px-3 py-1 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded text-sm hover:from-blue-500 hover:to-cyan-400 flex items-center gap-1"
            >
              <PencilIcon className="h-4 w-4" />
              Edit
            </button>
          )}
        </div>
        {yamlError && (
          <div className="mb-2 p-2 bg-red-500/10 text-red-400 text-sm rounded-lg border border-red-500/30">{yamlError}</div>
        )}
        <textarea
          value={yamlContent}
          onChange={(e) => { setYamlContent(e.target.value); setYamlError(null); }}
          readOnly={!editMode}
          className={`w-full h-96 p-4 font-mono text-xs rounded-lg bg-slate-900 text-slate-100 focus:outline-none border ${editMode ? 'border-cyan-500' : 'border-slate-700'}`}
          spellCheck={false}
        />
      </div>
    )
  }

  const renderMetadata = () => {
    if (!data?.metadata) return <p className="text-slate-500">No metadata</p>
    
    return (
      <div className="space-y-4">
        <div>
          <h4 className="text-xs text-slate-400 mb-2">Name</h4>
          <p className="text-sm font-mono text-white">{data.metadata.name}</p>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-2">Namespace</h4>
          <p className="text-sm font-mono text-white">{data.metadata.namespace || '-'}</p>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-2">UID</h4>
          <p className="text-sm font-mono text-white">{data.metadata.uid}</p>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-2">Labels</h4>
          <pre className="text-sm font-mono bg-slate-800 p-3 rounded-lg overflow-auto text-slate-300 border border-slate-700">
            {yaml.dump(data.metadata.labels || {}, { indent: 2 })}
          </pre>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-2">Annotations</h4>
          <pre className="text-sm font-mono bg-slate-800 p-3 rounded-lg overflow-auto text-slate-300 border border-slate-700">
            {yaml.dump(data.metadata.annotations || {}, { indent: 2 })}
          </pre>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-2">Creation Timestamp</h4>
          <p className="text-sm font-mono text-white">{data.metadata.creationTimestamp || '-'}</p>
        </div>
      </div>
    )
  }

  const renderSpec = () => {
    if (!data?.spec) return <p className="text-slate-500">No spec</p>
    
    return (
      <pre className="text-sm font-mono bg-slate-800 p-4 rounded-lg overflow-auto max-h-96 text-slate-300 border border-slate-700">
        {yaml.dump(data.spec, { indent: 2 })}
      </pre>
    )
  }

  const renderStatus = () => {
    if (!data?.status) return <p className="text-slate-500">No status</p>
    
    return (
      <pre className="text-sm font-mono bg-slate-800 p-4 rounded-lg overflow-auto max-h-96 text-slate-300 border border-slate-700">
        {yaml.dump(data.status, { indent: 2 })}
      </pre>
    )
  }

  const renderIngressRules = () => {
    if (!data?.rules || data.rules.length === 0) return <p className="text-slate-500">No rules</p>
    
    return (
      <div className="space-y-4">
        {data.rules.map((rule, idx) => (
          <div key={idx} className="border border-slate-700 rounded-lg p-4 bg-slate-800/30">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-sm font-semibold text-white">Rule {idx + 1}</span>
              <span className="px-2 py-0.5 bg-purple-600/20 text-purple-400 text-xs rounded border border-purple-500/30">HTTP</span>
            </div>
            <div className="space-y-3">
              <div>
                <h5 className="text-xs text-slate-400 mb-1">Host</h5>
                <p className="text-sm font-mono text-cyan-400">{rule.host || '*'}</p>
              </div>
              {rule.paths && rule.paths.length > 0 && (
                <div>
                  <h5 className="text-xs text-slate-400 mb-2">Paths</h5>
                  <div className="space-y-2">
                    {rule.paths.map((path, pathIdx) => (
                      <div key={pathIdx} className="bg-slate-800/50 p-3 rounded border border-slate-700">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-slate-500">Path:</span>
                          <span className="text-sm font-mono text-white">{path.path}</span>
                          <span className="px-1.5 py-0.5 bg-blue-600/20 text-blue-400 text-xs rounded">{path.path_type}</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-slate-400">Backend:</span>
                          <span className="text-green-400">{path.backend_service}</span>
                          <span className="text-slate-500">:</span>
                          <span className="text-green-400">{path.backend_port}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {data.tls && data.tls.length > 0 && (
          <div className="border-t border-slate-700 pt-4 mt-4">
            <h4 className="text-sm font-semibold text-white mb-3">TLS Configuration</h4>
            <div className="space-y-3">
              {data.tls.map((tls, idx) => (
                <div key={idx} className="border border-slate-700 rounded-lg p-4 bg-slate-800/30">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 bg-green-600/20 text-green-400 text-xs rounded border border-green-500/30">TLS Enabled</span>
                    {tls.secret_name && (
                      <span className="text-xs text-slate-400">Secret: <span className="text-white font-mono">{tls.secret_name}</span></span>
                    )}
                  </div>
                  {tls.hosts && tls.hosts.length > 0 && (
                    <div>
                      <span className="text-xs text-slate-400">Hosts:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {tls.hosts.map((host, hostIdx) => (
                          <span key={hostIdx} className="px-2 py-1 bg-green-600/20 text-green-400 text-xs rounded border border-green-500/30">
                            {host}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderRules = () => {
    if (!data?.rules || data.rules.length === 0) return <p className="text-slate-500">No rules</p>
    
    return (
      <div className="space-y-4">
        {data.rules.map((rule, idx) => (
          <div key={idx} className="border border-slate-700 rounded-lg p-4 bg-slate-800/30">
            <h4 className="text-sm font-semibold text-white mb-3">Rule {idx + 1}</h4>
            <div className="space-y-3">
              <div>
                <h5 className="text-xs text-slate-400 mb-1">API Groups</h5>
                <div className="flex flex-wrap gap-1">
                  {rule.apiGroups?.length > 0 ? (
                    rule.apiGroups.map((ag, i) => (
                      <span key={i} className="px-2 py-1 bg-blue-600/20 text-blue-400 text-xs rounded border border-blue-500/30">
                        {ag || '*'}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">None</span>
                  )}
                </div>
              </div>
              <div>
                <h5 className="text-xs text-slate-400 mb-1">Resources</h5>
                <div className="flex flex-wrap gap-1">
                  {rule.resources?.length > 0 ? (
                    rule.resources.map((r, i) => (
                      <span key={i} className="px-2 py-1 bg-green-600/20 text-green-400 text-xs rounded border border-green-500/30">
                        {r}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">None</span>
                  )}
                </div>
              </div>
              <div>
                <h5 className="text-xs text-slate-400 mb-1">Verbs</h5>
                <div className="flex flex-wrap gap-1">
                  {rule.verbs?.length > 0 ? (
                    rule.verbs.map((v, i) => (
                      <span key={i} className="px-2 py-1 bg-purple-600/20 text-purple-400 text-xs rounded border border-purple-500/30">
                        {v}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">None</span>
                  )}
                </div>
              </div>
              {rule.nonResourceURLs?.length > 0 && (
                <div>
                  <h5 className="text-xs text-slate-400 mb-1">Non-Resource URLs</h5>
                  <div className="flex flex-wrap gap-1">
                    {rule.nonResourceURLs.map((url, i) => (
                      <span key={i} className="px-2 py-1 bg-yellow-600/20 text-yellow-400 text-xs rounded border border-yellow-500/30">
                        {url}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {rule.resourceNames?.length > 0 && (
                <div>
                  <h5 className="text-xs text-slate-400 mb-1">Resource Names</h5>
                  <div className="flex flex-wrap gap-1">
                    {rule.resourceNames.map((name, i) => (
                      <span key={i} className="px-2 py-1 bg-slate-600/30 text-slate-300 text-xs rounded border border-slate-500/50">
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderRoleRef = () => {
    if (!data?.roleRef) return <p className="text-slate-500">No roleRef</p>
    
    return (
      <div className="space-y-4">
        <div>
          <h4 className="text-xs text-slate-400 mb-1">API Group</h4>
          <p className="text-sm font-mono text-white">{data.roleRef.apiGroup || '-'}</p>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-1">Kind</h4>
          <p className="text-sm font-mono text-white">{data.roleRef.kind || '-'}</p>
        </div>
        <div>
          <h4 className="text-xs text-slate-400 mb-1">Name</h4>
          <p className="text-sm font-mono text-white">{data.roleRef.name || '-'}</p>
        </div>
      </div>
    )
  }

  const renderSubjects = () => {
    if (!data?.subjects || data.subjects.length === 0) return <p className="text-slate-500">No subjects</p>
    
    return (
      <div className="space-y-3">
        {data.subjects.map((subject, idx) => (
          <div key={idx} className="border border-slate-700 rounded-lg p-4 bg-slate-800/30">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <h4 className="text-xs text-slate-400 mb-1">Kind</h4>
                <p className="text-sm font-medium text-white">{subject.kind || '-'}</p>
              </div>
              <div>
                <h4 className="text-xs text-slate-400 mb-1">Name</h4>
                <p className="text-sm font-mono text-white">{subject.name || '-'}</p>
              </div>
              <div>
                <h4 className="text-xs text-slate-400 mb-1">Namespace</h4>
                <p className="text-sm font-mono text-white">{subject.namespace || '-'}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose} />

      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative w-full max-w-4xl rounded-xl glass-panel shadow-2xl max-h-[90vh] flex flex-col">
          {notification && (
            <div className={`absolute top-4 right-4 z-50 px-4 py-2 rounded-lg shadow-lg ${
              notification.type === 'success' ? 'bg-green-600 text-white' :
              notification.type === 'error' ? 'bg-red-600 text-white' :
              'bg-blue-600 text-white'
            }`}>
              {notification.message}
            </div>
          )}

          <div className="border-b border-slate-700/50 px-6 py-4 flex items-center justify-between flex-shrink-0">
            <div>
              <h2 className="text-lg font-semibold text-white">{title}</h2>
              <p className="text-sm text-slate-400">{data?.kind}</p>
            </div>
            <div className="flex items-center gap-2">
              {onDelete ? (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="flex items-center gap-2 px-3 py-2 bg-red-600/20 text-red-400 border border-red-500/30 rounded-lg hover:bg-red-600/30 hover:text-red-300 transition-colors"
                >
                  <TrashIcon className="h-4 w-4" />
                  Delete
                </button>
              ) : null}
              <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
          </div>

          <div className="border-b border-slate-700/50 px-6 flex-shrink-0">
            <nav className="-mb-px flex space-x-4">
              {(customTabs || tabs).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'border-cyan-500 text-cyan-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-500'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="px-6 py-4 overflow-y-auto flex-1">
            {loading ? (
              <div className="text-center py-8">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500"></div>
                <p className="mt-2 text-slate-400">Loading...</p>
              </div>
            ) : (data || customContent) ? (
              <>
                {activeTab === 'overview' && (
                  typeof customContent === 'object' && customContent?.overview 
                    ? customContent.overview 
                    : renderOverview()
                )}
                {activeTab === 'yaml' && (data || fullYaml || yamlLoading) && renderYaml()}
                {activeTab === 'metadata' && data && renderMetadata()}
                {activeTab === 'spec' && data && renderSpec()}
                {activeTab === 'status' && data && renderStatus()}
                {activeTab === 'rules' && data && (
                  resourceType === 'ingresses' || data.kind === 'Ingress'
                    ? renderIngressRules()
                    : renderRules()
                )}
                {activeTab === 'roleref' && data && renderRoleRef()}
                {activeTab === 'subjects' && data && renderSubjects()}
                {activeTab === 'events' && (
                  typeof customContent === 'object' && customContent?.events
                    ? customContent.events
                    : (events && events.length > 0 ? (
                        <div className="space-y-4">
                          {events.slice(0, 50).map((event, idx) => (
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
                      ) : (
                        <p className="text-slate-500">No events found</p>
                      ))
                )}
                {activeTab === 'logs' && renderLogs()}
                {activeTab === 'terminal' && resourceType === 'pods' && (
                  <div className="h-96">
                    <PodTerminal
                      podName={title}
                      namespace={data?.metadata?.namespace || data?.namespace || ''}
                      container={selectedContainer}
                    />
                  </div>
                )}
              </>
            ) : (
              <p className="text-slate-400 py-8 text-center">No data</p>
            )}
          </div>

          <div className="border-t border-slate-700/50 px-6 py-4 bg-slate-800/30 rounded-b-xl flex justify-end flex-shrink-0">
            <button onClick={onClose} className="px-4 py-2 text-slate-300 border border-slate-600 rounded-lg hover:bg-slate-700/50 hover:text-white transition-colors">
              Close
            </button>
          </div>

          {showDeleteConfirm && (
            <div className="fixed inset-0 z-[70]">
              <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowDeleteConfirm(false)} />
              <div className="fixed inset-0 flex items-center justify-center p-4 pointer-events-none">
                <div className="pointer-events-auto relative w-full max-w-md bg-slate-800 rounded-xl shadow-2xl border border-slate-700 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                      <TrashIcon className="h-5 w-5 text-red-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-white">Delete Resource</h3>
                  </div>
                  <p className="text-slate-300 mb-6">
                    Are you sure you want to delete <span className="font-medium text-white">{title}</span>? 
                    This action cannot be undone.
                  </p>
                  <div className="flex justify-end gap-3">
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-4 py-2 text-slate-300 hover:text-white transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      {deleting ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                          Deleting...
                        </>
                      ) : (
                        <>
                          <TrashIcon className="h-4 w-4" />
                          Delete
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}