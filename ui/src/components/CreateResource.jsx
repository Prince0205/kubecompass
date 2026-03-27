/**
 * CreateResource Component
 * Modal for creating Kubernetes resources with form fields
 */

import React, { useState } from 'react'
import { XMarkIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import yaml from 'js-yaml'
import { v1API } from '../api'
import { useAppContext } from '../context/AppContext'

export default function CreateResource({ isOpen, resourceType, onClose, onSuccess }) {
  const { namespaces, activeNamespace } = useAppContext()
  const [formData, setFormData] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [labels, setLabels] = useState([{ key: '', value: '' }])
  const [annotations, setAnnotations] = useState([{ key: '', value: '' }])
  const [containers, setContainers] = useState([{ name: '', image: '', port: '' }])
  const [initContainers, setInitContainers] = useState([{ name: '', image: '', command: '' }])
  const [volumes, setVolumes] = useState([{ name: '', type: 'emptyDir', size: '', mountPath: '', configMapName: '', secretName: '' }])
  const [envVars, setEnvVars] = useState([{ name: '', value: '' }])
  const [rules, setRules] = useState([{ apiGroups: '', resources: '', verbs: '', nonResourceURLs: '', resourceNames: '' }])
  const [roleRef, setRoleRef] = useState({ apiGroup: '', kind: 'Role', name: '' })
  const [subjects, setSubjects] = useState([{ kind: 'ServiceAccount', name: '', namespace: '' }])
  const [nodeSelector, setNodeSelector] = useState([{ key: '', value: '' }])
  const [tolerations, setTolerations] = useState([{ key: '', operator: 'Equal', value: '', effect: '' }])

  if (!isOpen) return null

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleLabelChange = (index, field, value) => {
    const newLabels = [...labels]
    newLabels[index][field] = value
    setLabels(newLabels)
  }

  const addLabel = () => {
    setLabels([...labels, { key: '', value: '' }])
  }

  const removeLabel = (index) => {
    setLabels(labels.filter((_, i) => i !== index))
  }

  const handleAnnotationChange = (index, field, value) => {
    const newAnnotations = [...annotations]
    newAnnotations[index][field] = value
    setAnnotations(newAnnotations)
  }

  const addAnnotation = () => {
    setAnnotations([...annotations, { key: '', value: '' }])
  }

  const removeAnnotation = (index) => {
    setAnnotations(annotations.filter((_, i) => i !== index))
  }

  const handleContainerChange = (index, field, value) => {
    const newContainers = [...containers]
    newContainers[index][field] = value
    setContainers(newContainers)
  }

  const addContainer = () => {
    setContainers([...containers, { name: '', image: '', port: '' }])
  }

  const removeContainer = (index) => {
    setContainers(containers.filter((_, i) => i !== index))
  }

  const handleInitContainerChange = (index, field, value) => {
    const newInit = [...initContainers]
    newInit[index][field] = value
    setInitContainers(newInit)
  }

  const addInitContainer = () => {
    setInitContainers([...initContainers, { name: '', image: '', command: '' }])
  }

  const removeInitContainer = (index) => {
    setInitContainers(initContainers.filter((_, i) => i !== index))
  }

  const handleVolumeChange = (index, field, value) => {
    const newVolumes = [...volumes]
    newVolumes[index][field] = value
    setVolumes(newVolumes)
  }

  const addVolume = () => {
    setVolumes([...volumes, { name: '', type: 'emptyDir', size: '', mountPath: '', configMapName: '', secretName: '' }])
  }

  const removeVolume = (index) => {
    setVolumes(volumes.filter((_, i) => i !== index))
  }

  const handleEnvVarChange = (index, field, value) => {
    const newEnvVars = [...envVars]
    newEnvVars[index][field] = value
    setEnvVars(newEnvVars)
  }

  const addEnvVar = () => {
    setEnvVars([...envVars, { name: '', value: '' }])
  }

  const removeEnvVar = (index) => {
    setEnvVars(envVars.filter((_, i) => i !== index))
  }

  const handleRuleChange = (index, field, value) => {
    const newRules = [...rules]
    newRules[index][field] = value
    setRules(newRules)
  }

  const addRule = () => {
    setRules([...rules, { apiGroups: '', resources: '', verbs: '', nonResourceURLs: '', resourceNames: '' }])
  }

  const removeRule = (index) => {
    setRules(rules.filter((_, i) => i !== index))
  }

  const handleRoleRefChange = (field, value) => {
    setRoleRef(prev => ({ ...prev, [field]: value }))
  }

  const handleSubjectChange = (index, field, value) => {
    const newSubjects = [...subjects]
    newSubjects[index][field] = value
    setSubjects(newSubjects)
  }

  const addSubject = () => {
    setSubjects([...subjects, { kind: 'ServiceAccount', name: '', namespace: '' }])
  }

  const removeSubject = (index) => {
    setSubjects(subjects.filter((_, i) => i !== index))
  }

  const handleNodeSelectorChange = (index, field, value) => {
    const newNodeSelector = [...nodeSelector]
    newNodeSelector[index][field] = value
    setNodeSelector(newNodeSelector)
  }

  const addNodeSelector = () => {
    setNodeSelector([...nodeSelector, { key: '', value: '' }])
  }

  const removeNodeSelector = (index) => {
    setNodeSelector(nodeSelector.filter((_, i) => i !== index))
  }

  const handleTolerationChange = (index, field, value) => {
    const newTolerations = [...tolerations]
    newTolerations[index][field] = value
    setTolerations(newTolerations)
  }

  const addToleration = () => {
    setTolerations([...tolerations, { key: '', operator: 'Equal', value: '', effect: '' }])
  }

  const removeToleration = (index) => {
    setTolerations(tolerations.filter((_, i) => i !== index))
  }

  const resourceLabels = {
    namespace: 'Namespace',
    deployment: 'Deployment',
    pod: 'Pod',
    statefulset: 'StatefulSet',
    daemonset: 'DaemonSet',
    job: 'Job',
    cronjob: 'CronJob',
    configmap: 'ConfigMap',
    secret: 'Secret',
    service: 'Service',
    ingress: 'Ingress',
    pvc: 'PersistentVolumeClaim',
    pv: 'PersistentVolume',
    quota: 'ResourceQuota',
    limitrange: 'LimitRange',
    networkpolicy: 'NetworkPolicy',
    hpa: 'HorizontalPodAutoscaler',
    storageclass: 'StorageClass',
    role: 'Role',
    clusterrole: 'ClusterRole',
    rolebinding: 'RoleBinding',
    clusterrolebinding: 'ClusterRoleBinding',
    serviceaccount: 'ServiceAccount',
  }

  const resourceTypeMap = {
    namespace: 'namespace',
    deployment: 'deployments',
    pod: 'pods',
    statefulset: 'statefulsets',
    daemonset: 'daemonsets',
    job: 'jobs',
    cronjob: 'cronjobs',
    configmap: 'configmaps',
    secret: 'secrets',
    service: 'services',
    ingress: 'ingresses',
    pvc: 'pvcs',
    pv: 'pvs',
    quota: 'quotas',
    limitrange: 'limitranges',
    networkpolicy: 'networkpolicies',
    hpa: 'hpas',
    storageclass: 'storageclasses',
    role: 'roles',
    clusterrole: 'clusterroles',
    rolebinding: 'rolebindings',
    clusterrolebinding: 'clusterrolebindings',
    serviceaccount: 'serviceaccounts',
  }

  const getApiResourceType = () => resourceTypeMap[resourceType] || resourceType

  const generateYaml = () => {
    const name = formData.name || 'new-resource'
    const labelsObj = {}
    labels.forEach(l => {
      if (l.key && l.value) labelsObj[l.key] = l.value
    })

    const annotationsObj = {}
    annotations.forEach(a => {
      if (a.key && a.value) annotationsObj[a.key] = a.value
    })

    const nodeSelectorObj = {}
    nodeSelector.forEach(ns => {
      if (ns.key && ns.value) nodeSelectorObj[ns.key] = ns.value
    })

    const tolerationsArr = tolerations.filter(t => t.key || t.value).map(t => {
      const toleration = {}
      if (t.key) toleration.key = t.key
      if (t.operator) toleration.operator = t.operator
      if (t.value) toleration.value = t.value
      if (t.effect) toleration.effect = t.effect
      return toleration
    })

    const baseManifest = {
      apiVersion: resourceType === 'hpa' ? 'autoscaling/v2' :
                  ['role', 'clusterrole', 'rolebinding', 'clusterrolebinding'].includes(resourceType) ? 'rbac.authorization.k8s.io/v1' : 'v1',
      kind: resourceType === 'statefulset' ? 'StatefulSet' : 
            resourceType === 'daemonset' ? 'DaemonSet' :
            resourceType === 'cronjob' ? 'CronJob' :
            resourceType === 'configmap' ? 'ConfigMap' :
            resourceType === 'secret' ? 'Secret' :
            resourceType === 'service' ? 'Service' :
            resourceType === 'ingress' ? 'Ingress' :
            resourceType === 'pvc' ? 'PersistentVolumeClaim' :
            resourceType === 'quota' ? 'ResourceQuota' :
            resourceType === 'limitrange' ? 'LimitRange' :
            resourceType === 'networkpolicy' ? 'NetworkPolicy' :
            resourceType === 'hpa' ? 'HorizontalPodAutoscaler' :
            resourceType === 'storageclass' ? 'StorageClass' :
            resourceType === 'namespace' ? 'Namespace' :
            resourceType === 'job' ? 'Job' : 'Deployment',
      metadata: {
        name: name,
        namespace: resourceType === 'namespace' || ['clusterrole', 'clusterrolebinding', 'storageclass', 'pv'].includes(resourceType) ? undefined : (formData.namespace || 'default'),
      },
    }

    if (baseManifest.metadata) {
      if (Object.keys(labelsObj).length > 0) baseManifest.metadata.labels = labelsObj
      if (Object.keys(annotationsObj).length > 0) baseManifest.metadata.annotations = annotationsObj
    }

    switch (resourceType) {
      case 'namespace':
        break
      case 'pod':
        const podContainers = containers.filter(c => c.name).map(c => {
          const container = { name: c.name, image: c.image || 'nginx:latest' }
          if (c.port) container.ports = [{ containerPort: parseInt(c.port) }]
          const envList = envVars.filter(e => e.name).map(e => ({ name: e.name, value: e.value }))
          if (envList.length > 0) container.env = envList
          const vmList = volumes.filter(v => v.mountPath && v.name).map(v => ({ name: v.name, mountPath: v.mountPath }))
          if (vmList.length > 0) container.volumeMounts = vmList
          if (c.livenessProbe) container.livenessProbe = JSON.parse(c.livenessProbe)
          if (c.readinessProbe) container.readinessProbe = JSON.parse(c.readinessProbe)
          if (c.startupProbe) container.startupProbe = JSON.parse(c.startupProbe)
          if (c.resources) container.resources = JSON.parse(c.resources)
          if (c.command) container.command = c.command.split(' ').filter(x => x)
          return container
        })

        const podInitContainers = initContainers.filter(c => c.name).map(c => {
          const container = { name: c.name, image: c.image || 'busybox' }
          if (c.command) container.command = c.command.split(' ').filter(x => x)
          return container
        })

        const podVolumes = volumes.filter(v => v.name).map(v => {
          if (v.type === 'emptyDir') return { name: v.name, emptyDir: v.size ? { sizeLimit: v.size } : {} }
          if (v.type === 'configMap') return { name: v.name, configMap: { name: v.configMapName } }
          if (v.type === 'secret') return { name: v.name, secret: { secretName: v.secretName } }
          if (v.type === 'hostPath') return { name: v.name, hostPath: { path: v.mountPath } }
          if (v.type === 'persistentVolumeClaim') return { name: v.name, persistentVolumeClaim: { claimName: v.mountPath } }
          return { name: v.name, emptyDir: {} }
        })

        baseManifest.spec = {
          restartPolicy: formData.podRestartPolicy || 'Always',
          containers: podContainers,
        }

        if (podInitContainers.length > 0) baseManifest.spec.initContainers = podInitContainers
        if (podVolumes.length > 0) baseManifest.spec.volumes = podVolumes

        const podNodeSelector = {}
        nodeSelector.forEach(ns => { if (ns.key && ns.value) podNodeSelector[ns.key] = ns.value })
        if (Object.keys(podNodeSelector).length > 0) baseManifest.spec.nodeSelector = podNodeSelector

        const podTolerations = tolerations.filter(t => t.key || t.value).map(t => {
          const toleration = {}
          if (t.key) toleration.key = t.key
          if (t.operator) toleration.operator = t.operator
          if (t.value) toleration.value = t.value
          if (t.effect) toleration.effect = t.effect
          return toleration
        })
        if (podTolerations.length > 0) baseManifest.spec.tolerations = podTolerations

        if (formData.dnsPolicy) baseManifest.spec.dnsPolicy = formData.dnsPolicy
        if (formData.hostNetwork === 'true') baseManifest.spec.hostNetwork = true
        if (formData.hostPID === 'true') baseManifest.spec.hostPID = true
        if (formData.hostIPC === 'true') baseManifest.spec.hostIPC = true
        if (formData.priorityClassName) baseManifest.spec.priorityClassName = formData.priorityClassName
        if (formData.imagePullSecrets) {
          baseManifest.spec.imagePullSecrets = formData.imagePullSecrets.split(',').map(s => ({ name: s.trim() })).filter(s => s.name)
        }
        break
      case 'deployment':
      case 'statefulset':
      case 'daemonset':
        const containersSpec = containers.filter(c => c.name).map(c => {
          const container = { name: c.name, image: c.image || 'nginx:latest' }
          if (c.port) container.ports = [{ containerPort: parseInt(c.port) }]
          const envList = envVars.filter(e => e.name).map(e => ({ name: e.name, value: e.value }))
          if (envList.length > 0) container.env = envList
          const vmList = volumes.filter(v => v.mountPath && v.name).map(v => ({ name: v.name, mountPath: v.mountPath }))
          if (vmList.length > 0) container.volumeMounts = vmList
          return container
        })

        const initContainersSpec = initContainers.filter(c => c.name).map(c => {
          const container = { name: c.name, image: c.image || 'busybox' }
          if (c.command) container.command = c.command.split(' ').filter(x => x)
          return container
        })

        const volumesSpec = volumes.filter(v => v.name).map(v => {
          if (v.type === 'emptyDir') return { name: v.name, emptyDir: v.size ? { sizeLimit: v.size } : {} }
          if (v.type === 'configMap') return { name: v.name, configMap: { name: v.configMapName } }
          if (v.type === 'secret') return { name: v.name, secret: { secretName: v.secretName } }
          return { name: v.name, emptyDir: {} }
        })

        baseManifest.spec = {
          replicas: parseInt(formData.replicas) || 1,
          selector: { matchLabels: { app: name } },
          template: {
            metadata: { labels: { app: name } },
            spec: { containers: containersSpec },
          },
        }

        if (initContainersSpec.length > 0) baseManifest.spec.template.spec.initContainers = initContainersSpec
        if (volumesSpec.length > 0) baseManifest.spec.template.spec.volumes = volumesSpec
        if (Object.keys(nodeSelectorObj).length > 0) baseManifest.spec.template.spec.nodeSelector = nodeSelectorObj
        if (tolerationsArr.length > 0) baseManifest.spec.template.spec.tolerations = tolerationsArr

        if (resourceType === 'deployment') {
          baseManifest.spec.strategy = { type: formData.strategyType || 'RollingUpdate', rollingUpdate: { maxSurge: 1, maxUnavailable: 0 } }
        }
        if (resourceType === 'statefulset') {
          baseManifest.spec.serviceName = formData.serviceName || name
          if (formData.volumeSize) {
            baseManifest.spec.volumeClaimTemplates = [{
              metadata: { name: formData.volumeClaimTemplate || 'data' },
              spec: {
                accessModes: [formData.volumeAccessMode || 'ReadWriteOnce'],
                resources: { requests: { storage: formData.volumeSize } },
                storageClassName: formData.volumeStorageClass || 'standard',
              },
            }]
          }
        }
        break
      case 'job':
        baseManifest.spec = {
          backoffLimit: parseInt(formData.backoffLimit) || 6,
          ttlSecondsAfterFinished: formData.ttlSecondsAfterFinished ? parseInt(formData.ttlSecondsAfterFinished) : undefined,
          completions: formData.completions ? parseInt(formData.completions) : 1,
          parallelism: formData.parallelism ? parseInt(formData.parallelism) : 1,
          activeDeadlineSeconds: formData.activeDeadlineSeconds ? parseInt(formData.activeDeadlineSeconds) : undefined,
          template: {
            spec: {
              restartPolicy: formData.jobRestartPolicy || 'Never',
              containers: [{ name: name, image: formData.image || 'busybox', command: formData.command ? formData.command.split(' ').filter(x => x) : ['echo', 'hello'] }],
            },
          },
        }
        if (Object.keys(nodeSelectorObj).length > 0) baseManifest.spec.template.spec.nodeSelector = nodeSelectorObj
        if (tolerationsArr.length > 0) baseManifest.spec.template.spec.tolerations = tolerationsArr
        break
      case 'cronjob':
        baseManifest.spec = {
          schedule: formData.schedule || '*/5 * * * *',
          concurrencyPolicy: formData.concurrencyPolicy || 'Allow',
          suspend: formData.suspend === 'true',
          successfulJobsHistoryLimit: formData.successfulJobsHistoryLimit ? parseInt(formData.successfulJobsHistoryLimit) : 3,
          failedJobsHistoryLimit: formData.failedJobsHistoryLimit ? parseInt(formData.failedJobsHistoryLimit) : 1,
          startingDeadlineSeconds: formData.startingDeadlineSeconds ? parseInt(formData.startingDeadlineSeconds) : undefined,
          jobTemplate: {
            spec: {
              template: {
                spec: {
                  restartPolicy: formData.cronJobRestartPolicy || 'Never',
                  containers: [{ name: name, image: formData.image || 'busybox', command: formData.command ? formData.command.split(' ').filter(x => x) : ['echo', 'hello'] }],
                },
              },
            },
          },
        }
        break
      case 'configmap':
        baseManifest.data = {}
        envVars.forEach(e => { if (e.name) baseManifest.data[e.name] = e.value })
        break
      case 'secret':
        baseManifest.type = formData.secretType || 'Opaque'
        baseManifest.data = {}
        envVars.forEach(e => { if (e.name && e.value) baseManifest.data[e.name] = btoa(e.value) })
        break
      case 'service':
        baseManifest.spec = {
          type: formData.serviceType || 'ClusterIP',
          sessionAffinity: formData.sessionAffinity || 'None',
          ports: formData.port ? [{ port: parseInt(formData.port), targetPort: formData.targetPort ? parseInt(formData.targetPort) : parseInt(formData.port), protocol: formData.protocol || 'TCP' }] : [],
        }
        baseManifest.spec.selector = formData.selector ? (() => { try { return JSON.parse(formData.selector) } catch { return { app: name } } })() : { app: name }
        if (formData.externalIPs) baseManifest.spec.externalIPs = formData.externalIPs.split(',').map(x => x.trim()).filter(x => x)
        if (formData.loadBalancerIP) baseManifest.spec.loadBalancerIP = formData.loadBalancerIP
        break
      case 'ingress':
        baseManifest.spec = {
          ingressClassName: formData.ingressClass || undefined,
          tls: formData.tlsSecret ? [{ secretName: formData.tlsSecret }] : [],
          rules: formData.host ? [{
            host: formData.host,
            http: {
              paths: [{ path: formData.ingressPath || '/', pathType: formData.ingressPathType || 'Prefix', backend: { service: { name: formData.serviceName || name, port: { number: parseInt(formData.ingressPort) || 80 } } } }],
            },
          }] : [],
        }
        break
      case 'pvc':
        baseManifest.spec = {
          accessModes: [formData.accessMode || 'ReadWriteOnce'],
          resources: { requests: { storage: formData.storageSize || '1Gi' } },
          storageClassName: formData.storageClass || 'standard',
          volumeMode: formData.volumeMode || 'Filesystem',
        }
        break
      case 'pv':
        baseManifest.spec = {
          capacity: { storage: formData.capacity || '10Gi' },
          accessModes: [formData.pvAccessMode || 'ReadWriteOnce'],
          persistentVolumeReclaimPolicy: formData.reclaimPolicy || 'Retain',
          storageClassName: formData.storageClass || 'standard',
        }
        if (formData.hostPath) baseManifest.spec.hostPath = { path: formData.hostPath, type: formData.hostPathType || 'Directory' }
        if (formData.nfsServer) baseManifest.spec.nfs = { server: formData.nfsServer, path: formData.nfsPath || '/' }
        break
      case 'quota':
        baseManifest.spec = {
          hard: {
            requests: { memory: formData.memoryRequest || '128Mi', cpu: formData.cpuRequest || '100m', pods: formData.podsRequest ? parseInt(formData.podsRequest) : undefined },
            limits: { memory: formData.memoryLimit || '256Mi', cpu: formData.cpuLimit || '500m', pods: formData.podsLimit ? parseInt(formData.podsLimit) : undefined },
          },
        }
        break
      case 'limitrange':
        baseManifest.spec = {
          limits: [{
            type: formData.limitType || 'Container',
            max: formData.maxMemory ? { memory: formData.maxMemory } : undefined,
            min: formData.minMemory ? { memory: formData.minMemory } : undefined,
            default: formData.defaultMemory ? { memory: formData.defaultMemory } : undefined,
            defaultRequest: formData.defaultRequestMemory ? { memory: formData.defaultRequestMemory } : undefined,
          }],
        }
        break
      case 'networkpolicy':
        baseManifest.spec = {
          podSelector: { matchLabels: formData.podSelector ? (() => { try { return JSON.parse(formData.podSelector) } catch { return {} } })() : {} },
          policyTypes: formData.policyTypes ? formData.policyTypes.split(',').map(x => x.trim()) : ['Ingress', 'Egress'],
        }
        break
      case 'hpa':
        baseManifest.spec = {
          scaleTargetRef: { apiVersion: 'apps/v1', kind: formData.scaleTargetKind || 'Deployment', name: formData.scaleTargetName || name },
          minReplicas: parseInt(formData.minReplicas) || 1,
          maxReplicas: parseInt(formData.maxReplicas) || 10,
          metrics: [],
        }
        if (formData.targetCPUUtilization) baseManifest.spec.metrics.push({ type: 'Resource', resource: { name: 'cpu', target: { type: 'Utilization', averageUtilization: parseInt(formData.targetCPUUtilization) } } })
        break
      case 'storageclass':
        baseManifest.provisioner = formData.provisioner || 'kubernetes.io/gce-pd'
        baseManifest.reclaimPolicy = formData.reclaimPolicy || 'Delete'
        baseManifest.volumeBindingMode = formData.volumeBindingMode || 'Immediate'
        baseManifest.allowVolumeExpansion = formData.allowVolumeExpansion !== 'false'
        if (formData.mountOptions) baseManifest.mountOptions = formData.mountOptions.split(',').map(x => x.trim()).filter(x => x)
        break
      case 'role':
      case 'clusterrole':
        baseManifest.apiVersion = 'rbac.authorization.k8s.io/v1'
        baseManifest.kind = resourceType === 'clusterrole' ? 'ClusterRole' : 'Role'
        baseManifest.rules = rules.filter(r => r.apiGroups || r.resources || r.verbs || r.nonResourceURLs || r.resourceNames).map(r => {
          const rule = {}
          if (r.apiGroups) rule.apiGroups = r.apiGroups.split(',').map(s => s.trim()).filter(s => s)
          if (r.resources) rule.resources = r.resources.split(',').map(s => s.trim()).filter(s => s)
          if (r.verbs) rule.verbs = r.verbs.split(',').map(s => s.trim()).filter(s => s)
          if (r.nonResourceURLs) rule.nonResourceURLs = r.nonResourceURLs.split(',').map(s => s.trim()).filter(s => s)
          if (r.resourceNames) rule.resourceNames = r.resourceNames.split(',').map(s => s.trim()).filter(s => s)
          return rule
        })
        break
      case 'rolebinding':
      case 'clusterrolebinding':
        baseManifest.apiVersion = 'rbac.authorization.k8s.io/v1'
        baseManifest.kind = resourceType === 'clusterrolebinding' ? 'ClusterRoleBinding' : 'RoleBinding'
        baseManifest.roleRef = {
          apiGroup: roleRef.apiGroup || 'rbac.authorization.k8s.io',
          kind: roleRef.kind || 'Role',
          name: roleRef.name || formData.roleName || '',
        }
        baseManifest.subjects = subjects.filter(s => s.name).map(s => ({ kind: s.kind, name: s.name, namespace: s.namespace || undefined }))
        break
      case 'serviceaccount':
        baseManifest.kind = 'ServiceAccount'
        baseManifest.automountServiceAccountToken = formData.automountToken !== undefined ? formData.automountToken : true
        break
      default:
        break
    }
    return baseManifest
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const yamlObj = generateYaml()
      const yamlStr = yaml.dump(yamlObj, { lineWidth: -1 })
      if (resourceType === 'namespace') {
        await v1API.createNamespace(yamlObj.metadata.name)
      } else {
        await v1API.applyResource(getApiResourceType(), formData.name || 'new-resource', yamlStr)
      }
      if (onSuccess) onSuccess()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create resource')
    } finally {
      setSaving(false)
    }
  }

  const showNamespace = !['namespace', 'clusterrole', 'clusterrolebinding', 'storageclass', 'pv'].includes(resourceType)

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative w-full max-w-2xl rounded-xl glass-panel shadow-2xl max-h-[90vh] flex flex-col">
          <div className="border-b border-slate-700/50 px-6 py-4 flex items-center justify-between flex-shrink-0">
            <div>
              <h2 className="text-lg font-semibold text-white">Create {resourceLabels[resourceType] || resourceType}</h2>
              <p className="text-sm text-slate-400">Fill in the details for the new resource</p>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <form onSubmit={handleSubmit} className="px-6 py-4 overflow-y-auto flex-1">
            {error && <div className="mb-4 p-3 bg-red-500/10 text-red-400 rounded-lg border border-red-500/30">{error}</div>}
            <div className="space-y-4">
              <div className={showNamespace ? "grid grid-cols-2 gap-4" : ""}>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Name *</label>
                  <input type="text" required value={formData.name || ''} onChange={(e) => handleInputChange('name', e.target.value)} className="input-dark w-full text-sm" placeholder="resource-name" />
                </div>
                {showNamespace && (
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Namespace</label>
                    <select value={formData.namespace || (activeNamespace === '_all' ? 'default' : activeNamespace) || 'default'} onChange={(e) => handleInputChange('namespace', e.target.value)} className="input-dark w-full text-sm">
                      <option value="default">default</option>
                      {namespaces.filter(ns => ns.name !== 'default').map((ns) => (<option key={ns.name} value={ns.name}>{ns.name}</option>))}
                    </select>
                  </div>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-slate-300">Labels</label>
                  <button type="button" onClick={addLabel} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Label</button>
                </div>
                {labels.map((label, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <input type="text" value={label.key} onChange={(e) => handleLabelChange(idx, 'key', e.target.value)} className="input-dark flex-1 text-sm" placeholder="key" />
                    <input type="text" value={label.value} onChange={(e) => handleLabelChange(idx, 'value', e.target.value)} className="input-dark flex-1 text-sm" placeholder="value" />
                    <button type="button" onClick={() => removeLabel(idx)} className="text-red-400 hover:text-red-300"><TrashIcon className="h-5 w-5" /></button>
                  </div>
                ))}
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-slate-300">Annotations</label>
                  <button type="button" onClick={addAnnotation} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Annotation</button>
                </div>
                {annotations.map((annotation, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <input type="text" value={annotation.key} onChange={(e) => handleAnnotationChange(idx, 'key', e.target.value)} className="input-dark flex-1 text-sm" placeholder="key" />
                    <input type="text" value={annotation.value} onChange={(e) => handleAnnotationChange(idx, 'value', e.target.value)} className="input-dark flex-1 text-sm" placeholder="value" />
                    <button type="button" onClick={() => removeAnnotation(idx)} className="text-red-400 hover:text-red-300"><TrashIcon className="h-5 w-5" /></button>
                  </div>
                ))}
              </div>
              {['deployment', 'statefulset', 'daemonset', 'pod'].includes(resourceType) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Containers</label>
                    <button type="button" onClick={addContainer} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Container</button>
                  </div>
                  {containers.map((container, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/50 rounded mb-2 border border-slate-700">
                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <input type="text" value={container.name} onChange={(e) => handleContainerChange(idx, 'name', e.target.value)} className="input-dark w-full text-sm" placeholder="Container Name *" />
                        <input type="text" value={container.image} onChange={(e) => handleContainerChange(idx, 'image', e.target.value)} className="input-dark w-full text-sm" placeholder="Image (e.g., nginx:latest)" />
                        <input type="number" value={container.port} onChange={(e) => handleContainerChange(idx, 'port', e.target.value)} className="input-dark w-full text-sm" placeholder="Container Port" />
                      </div>
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <input type="text" value={container.command || ''} onChange={(e) => handleContainerChange(idx, 'command', e.target.value)} className="input-dark w-full text-sm" placeholder="Command (space-separated)" />
                        <input type="text" value={container.resources || ''} onChange={(e) => handleContainerChange(idx, 'resources', e.target.value)} className="input-dark w-full text-sm" placeholder='Resources JSON {"limits":{"cpu":"500m"}}' />
                      </div>
                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <input type="text" value={container.livenessProbe || ''} onChange={(e) => handleContainerChange(idx, 'livenessProbe', e.target.value)} className="input-dark w-full text-sm" placeholder='Liveness Probe JSON' />
                        <input type="text" value={container.readinessProbe || ''} onChange={(e) => handleContainerChange(idx, 'readinessProbe', e.target.value)} className="input-dark w-full text-sm" placeholder='Readiness Probe JSON' />
                        <input type="text" value={container.startupProbe || ''} onChange={(e) => handleContainerChange(idx, 'startupProbe', e.target.value)} className="input-dark w-full text-sm" placeholder='Startup Probe JSON' />
                      </div>
                      <div className="flex justify-end">
                        <button type="button" onClick={() => removeContainer(idx)} className="text-red-400 text-sm hover:text-red-300">Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {['deployment', 'statefulset', 'daemonset', 'pod', 'job', 'cronjob'].includes(resourceType) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Init Containers</label>
                    <button type="button" onClick={addInitContainer} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Init Container</button>
                  </div>
                  {initContainers.map((container, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/50 rounded mb-2 border border-slate-700">
                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <input type="text" value={container.name} onChange={(e) => handleInitContainerChange(idx, 'name', e.target.value)} className="input-dark w-full text-sm" placeholder="Container Name" />
                        <input type="text" value={container.image} onChange={(e) => handleInitContainerChange(idx, 'image', e.target.value)} className="input-dark w-full text-sm" placeholder="Image" />
                        <input type="text" value={container.command} onChange={(e) => handleInitContainerChange(idx, 'command', e.target.value)} className="input-dark w-full text-sm" placeholder="Command" />
                      </div>
                      <div className="flex justify-end">
                        <button type="button" onClick={() => removeInitContainer(idx)} className="text-red-400 text-sm hover:text-red-300">Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {['deployment', 'statefulset', 'daemonset', 'pod'].includes(resourceType) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Volumes</label>
                    <button type="button" onClick={addVolume} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Volume</button>
                  </div>
                  {volumes.map((volume, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/50 rounded mb-2 border border-slate-700">
                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <input type="text" value={volume.name} onChange={(e) => handleVolumeChange(idx, 'name', e.target.value)} className="input-dark w-full text-sm" placeholder="Volume Name *" />
                        <select value={volume.type} onChange={(e) => handleVolumeChange(idx, 'type', e.target.value)} className="input-dark w-full text-sm">
                          <option value="emptyDir">emptyDir</option>
                          <option value="configMap">ConfigMap</option>
                          <option value="secret">Secret</option>
                          <option value="hostPath">hostPath</option>
                          <option value="persistentVolumeClaim">PVC</option>
                        </select>
                        <input type="text" value={volume.size || volume.mountPath || ''} onChange={(e) => handleVolumeChange(idx, volume.type === 'emptyDir' ? 'size' : 'mountPath', e.target.value)} className="input-dark w-full text-sm" placeholder={volume.type === 'emptyDir' ? 'Size' : 'Mount Path / Path'} />
                      </div>
                      {volume.type === 'configMap' && <input type="text" value={volume.configMapName} onChange={(e) => handleVolumeChange(idx, 'configMapName', e.target.value)} className="input-dark w-full text-sm mb-2" placeholder="ConfigMap Name" />}
                      {volume.type === 'secret' && <input type="text" value={volume.secretName} onChange={(e) => handleVolumeChange(idx, 'secretName', e.target.value)} className="input-dark w-full text-sm mb-2" placeholder="Secret Name" />}
                      <div className="flex justify-end">
                        <button type="button" onClick={() => removeVolume(idx)} className="text-red-400 text-sm hover:text-red-300">Remove</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {['deployment', 'statefulset', 'daemonset', 'pod', 'job', 'cronjob'].includes(resourceType) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Node Selector</label>
                    <button type="button" onClick={addNodeSelector} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add</button>
                  </div>
                  {nodeSelector.map((ns, idx) => (
                    <div key={idx} className="flex gap-2 mb-2">
                      <input type="text" value={ns.key} onChange={(e) => handleNodeSelectorChange(idx, 'key', e.target.value)} className="input-dark flex-1 text-sm" placeholder="Key" />
                      <input type="text" value={ns.value} onChange={(e) => handleNodeSelectorChange(idx, 'value', e.target.value)} className="input-dark flex-1 text-sm" placeholder="Value" />
                      <button type="button" onClick={() => removeNodeSelector(idx)} className="text-red-400 hover:text-red-300"><TrashIcon className="h-5 w-5" /></button>
                    </div>
                  ))}
                </div>
              )}
              {['deployment', 'statefulset', 'daemonset', 'pod', 'job', 'cronjob'].includes(resourceType) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Tolerations</label>
                    <button type="button" onClick={addToleration} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add</button>
                  </div>
                  {tolerations.map((t, idx) => (
                    <div key={idx} className="flex gap-2 mb-2">
                      <input type="text" value={t.key} onChange={(e) => handleTolerationChange(idx, 'key', e.target.value)} className="input-dark flex-1 text-sm" placeholder="Key" />
                      <select value={t.operator} onChange={(e) => handleTolerationChange(idx, 'operator', e.target.value)} className="input-dark w-24 text-sm">
                        <option value="Equal">Equal</option>
                        <option value="Exists">Exists</option>
                      </select>
                      <input type="text" value={t.value} onChange={(e) => handleTolerationChange(idx, 'value', e.target.value)} className="input-dark flex-1 text-sm" placeholder="Value" />
                      <select value={t.effect} onChange={(e) => handleTolerationChange(idx, 'effect', e.target.value)} className="input-dark w-32 text-sm">
                        <option value="">No Effect</option>
                        <option value="NoSchedule">NoSchedule</option>
                        <option value="PreferNoSchedule">PreferNoSchedule</option>
                        <option value="NoExecute">NoExecute</option>
                      </select>
                      <button type="button" onClick={() => removeToleration(idx)} className="text-red-400 hover:text-red-300"><TrashIcon className="h-5 w-5" /></button>
                    </div>
                  ))}
                </div>
              )}
              {['deployment', 'statefulset', 'daemonset'].includes(resourceType) && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Replicas</label>
                    <input type="number" value={formData.replicas || 1} onChange={(e) => handleInputChange('replicas', e.target.value)} className="input-dark w-full text-sm" min="0" />
                  </div>
                  {resourceType === 'deployment' && (
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">Strategy Type</label>
                      <select value={formData.strategyType || 'RollingUpdate'} onChange={(e) => handleInputChange('strategyType', e.target.value)} className="input-dark w-full text-sm">
                        <option value="RollingUpdate">RollingUpdate</option>
                        <option value="Recreate">Recreate</option>
                      </select>
                    </div>
                  )}
                </div>
              )}
              {resourceType === 'statefulset' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Service Name</label>
                    <input type="text" value={formData.serviceName || ''} onChange={(e) => handleInputChange('serviceName', e.target.value)} className="input-dark w-full text-sm" placeholder="service-name" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Volume Size</label>
                    <input type="text" value={formData.volumeSize || ''} onChange={(e) => handleInputChange('volumeSize', e.target.value)} className="input-dark w-full text-sm" placeholder="1Gi" />
                  </div>
                </div>
              )}
              {resourceType === 'pod' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Restart Policy</label>
                    <select value={formData.podRestartPolicy || 'Always'} onChange={(e) => handleInputChange('podRestartPolicy', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Always">Always</option>
                      <option value="OnFailure">OnFailure</option>
                      <option value="Never">Never</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">DNS Policy</label>
                    <select value={formData.dnsPolicy || 'ClusterFirst'} onChange={(e) => handleInputChange('dnsPolicy', e.target.value)} className="input-dark w-full text-sm">
                      <option value="ClusterFirst">ClusterFirst</option>
                      <option value="ClusterFirstWithHostNet">ClusterFirstWithHostNet</option>
                      <option value="Default">Default</option>
                      <option value="None">None</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Host Network</label>
                    <select value={formData.hostNetwork || 'false'} onChange={(e) => handleInputChange('hostNetwork', e.target.value)} className="input-dark w-full text-sm">
                      <option value="false">False</option>
                      <option value="true">True</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Host PID</label>
                    <select value={formData.hostPID || 'false'} onChange={(e) => handleInputChange('hostPID', e.target.value)} className="input-dark w-full text-sm">
                      <option value="false">False</option>
                      <option value="true">True</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Host IPC</label>
                    <select value={formData.hostIPC || 'false'} onChange={(e) => handleInputChange('hostIPC', e.target.value)} className="input-dark w-full text-sm">
                      <option value="false">False</option>
                      <option value="true">True</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Image Pull Secrets</label>
                    <input type="text" value={formData.imagePullSecrets || ''} onChange={(e) => handleInputChange('imagePullSecrets', e.target.value)} className="input-dark w-full text-sm" placeholder="secret1,secret2" />
                  </div>
                </div>
              )}
              {['job', 'cronjob'].includes(resourceType) && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Image</label>
                  <input type="text" value={formData.image || ''} onChange={(e) => handleInputChange('image', e.target.value)} className="input-dark w-full text-sm" placeholder="busybox" />
                </div>
              )}
              {resourceType === 'job' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Backoff Limit</label>
                    <input type="number" value={formData.backoffLimit || 6} onChange={(e) => handleInputChange('backoffLimit', e.target.value)} className="input-dark w-full text-sm" min="0" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Restart Policy</label>
                    <select value={formData.jobRestartPolicy || 'Never'} onChange={(e) => handleInputChange('jobRestartPolicy', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Never">Never</option>
                      <option value="OnFailure">OnFailure</option>
                    </select>
                  </div>
                </div>
              )}
              {resourceType === 'cronjob' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Schedule (Cron) *</label>
                    <input type="text" value={formData.schedule || '*/5 * * * *'} onChange={(e) => handleInputChange('schedule', e.target.value)} className="input-dark w-full text-sm" placeholder="*/5 * * * *" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Concurrency Policy</label>
                    <select value={formData.concurrencyPolicy || 'Allow'} onChange={(e) => handleInputChange('concurrencyPolicy', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Allow">Allow</option>
                      <option value="Forbid">Forbid</option>
                      <option value="Replace">Replace</option>
                    </select>
                  </div>
                </div>
              )}
              {['configmap', 'secret'].includes(resourceType) && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Data</label>
                    <button type="button" onClick={addEnvVar} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Key</button>
                  </div>
                  {envVars.map((env, idx) => (
                    <div key={idx} className="flex gap-2 mb-2">
                      <input type="text" value={env.name} onChange={(e) => handleEnvVarChange(idx, 'name', e.target.value)} className="input-dark flex-1 text-sm" placeholder="key" />
                      <input type="text" value={env.value} onChange={(e) => handleEnvVarChange(idx, 'value', e.target.value)} className="input-dark flex-1 text-sm" placeholder="value" />
                      <button type="button" onClick={() => removeEnvVar(idx)} className="text-red-400 hover:text-red-300"><TrashIcon className="h-5 w-5" /></button>
                    </div>
                  ))}
                </div>
              )}
              {resourceType === 'secret' && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Secret Type</label>
                  <select value={formData.secretType || 'Opaque'} onChange={(e) => handleInputChange('secretType', e.target.value)} className="input-dark w-full text-sm">
                    <option value="Opaque">Opaque</option>
                    <option value="kubernetes.io/dockerconfigjson">kubernetes.io/dockerconfigjson</option>
                    <option value="kubernetes.io/tls">kubernetes.io/tls</option>
                    <option value="kubernetes.io/service-account-token">kubernetes.io/service-account-token</option>
                  </select>
                </div>
              )}
              {resourceType === 'service' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Service Type</label>
                    <select value={formData.serviceType || 'ClusterIP'} onChange={(e) => handleInputChange('serviceType', e.target.value)} className="input-dark w-full text-sm">
                      <option value="ClusterIP">ClusterIP</option>
                      <option value="NodePort">NodePort</option>
                      <option value="LoadBalancer">LoadBalancer</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Port</label>
                    <input type="number" value={formData.port || ''} onChange={(e) => handleInputChange('port', e.target.value)} className="input-dark w-full text-sm" placeholder="80" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Session Affinity</label>
                    <select value={formData.sessionAffinity || 'None'} onChange={(e) => handleInputChange('sessionAffinity', e.target.value)} className="input-dark w-full text-sm">
                      <option value="None">None</option>
                      <option value="ClientIP">ClientIP</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Protocol</label>
                    <select value={formData.protocol || 'TCP'} onChange={(e) => handleInputChange('protocol', e.target.value)} className="input-dark w-full text-sm">
                      <option value="TCP">TCP</option>
                      <option value="UDP">UDP</option>
                      <option value="SCTP">SCTP</option>
                    </select>
                  </div>
                </div>
              )}
              {resourceType === 'ingress' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Host</label>
                    <input type="text" value={formData.host || ''} onChange={(e) => handleInputChange('host', e.target.value)} className="input-dark w-full text-sm" placeholder="example.com" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Path</label>
                    <input type="text" value={formData.ingressPath || '/'} onChange={(e) => handleInputChange('ingressPath', e.target.value)} className="input-dark w-full text-sm" placeholder="/" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Service Name</label>
                    <input type="text" value={formData.serviceName || ''} onChange={(e) => handleInputChange('serviceName', e.target.value)} className="input-dark w-full text-sm" placeholder="backend-service" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Service Port</label>
                    <input type="number" value={formData.ingressPort || ''} onChange={(e) => handleInputChange('ingressPort', e.target.value)} className="input-dark w-full text-sm" placeholder="80" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Ingress Class</label>
                    <input type="text" value={formData.ingressClass || ''} onChange={(e) => handleInputChange('ingressClass', e.target.value)} className="input-dark w-full text-sm" placeholder="nginx" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">TLS Secret</label>
                    <input type="text" value={formData.tlsSecret || ''} onChange={(e) => handleInputChange('tlsSecret', e.target.value)} className="input-dark w-full text-sm" placeholder="tls-secret" />
                  </div>
                </div>
              )}
              {resourceType === 'pvc' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Storage Size</label>
                    <input type="text" value={formData.storageSize || '1Gi'} onChange={(e) => handleInputChange('storageSize', e.target.value)} className="input-dark w-full text-sm" placeholder="1Gi" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Storage Class</label>
                    <input type="text" value={formData.storageClass || 'standard'} onChange={(e) => handleInputChange('storageClass', e.target.value)} className="input-dark w-full text-sm" placeholder="standard" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Access Mode</label>
                    <select value={formData.accessMode || 'ReadWriteOnce'} onChange={(e) => handleInputChange('accessMode', e.target.value)} className="input-dark w-full text-sm">
                      <option value="ReadWriteOnce">ReadWriteOnce</option>
                      <option value="ReadOnlyMany">ReadOnlyMany</option>
                      <option value="ReadWriteMany">ReadWriteMany</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Volume Mode</label>
                    <select value={formData.volumeMode || 'Filesystem'} onChange={(e) => handleInputChange('volumeMode', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Filesystem">Filesystem</option>
                      <option value="Block">Block</option>
                    </select>
                  </div>
                </div>
              )}
              {resourceType === 'pv' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Capacity</label>
                    <input type="text" value={formData.capacity || '10Gi'} onChange={(e) => handleInputChange('capacity', e.target.value)} className="input-dark w-full text-sm" placeholder="10Gi" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Access Mode</label>
                    <select value={formData.pvAccessMode || 'ReadWriteOnce'} onChange={(e) => handleInputChange('pvAccessMode', e.target.value)} className="input-dark w-full text-sm">
                      <option value="ReadWriteOnce">ReadWriteOnce</option>
                      <option value="ReadOnlyMany">ReadOnlyMany</option>
                      <option value="ReadWriteMany">ReadWriteMany</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Reclaim Policy</label>
                    <select value={formData.reclaimPolicy || 'Retain'} onChange={(e) => handleInputChange('reclaimPolicy', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Retain">Retain</option>
                      <option value="Delete">Delete</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Host Path</label>
                    <input type="text" value={formData.hostPath || ''} onChange={(e) => handleInputChange('hostPath', e.target.value)} className="input-dark w-full text-sm" placeholder="/path/on/node" />
                  </div>
                </div>
              )}
              {resourceType === 'quota' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">CPU Request</label>
                    <input type="text" value={formData.cpuRequest || '100m'} onChange={(e) => handleInputChange('cpuRequest', e.target.value)} className="input-dark w-full text-sm" placeholder="100m" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Memory Request</label>
                    <input type="text" value={formData.memoryRequest || '128Mi'} onChange={(e) => handleInputChange('memoryRequest', e.target.value)} className="input-dark w-full text-sm" placeholder="128Mi" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">CPU Limit</label>
                    <input type="text" value={formData.cpuLimit || '500m'} onChange={(e) => handleInputChange('cpuLimit', e.target.value)} className="input-dark w-full text-sm" placeholder="500m" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Memory Limit</label>
                    <input type="text" value={formData.memoryLimit || '256Mi'} onChange={(e) => handleInputChange('memoryLimit', e.target.value)} className="input-dark w-full text-sm" placeholder="256Mi" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Pods Limit</label>
                    <input type="number" value={formData.podsLimit || ''} onChange={(e) => handleInputChange('podsLimit', e.target.value)} className="input-dark w-full text-sm" placeholder="10" />
                  </div>
                </div>
              )}
              {resourceType === 'networkpolicy' && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Pod Selector (JSON)</label>
                  <input type="text" value={formData.podSelector || ''} onChange={(e) => handleInputChange('podSelector', e.target.value)} className="input-dark w-full text-sm" placeholder='{"app": "myapp"}' />
                </div>
              )}
              {resourceType === 'hpa' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Min Replicas</label>
                    <input type="number" value={formData.minReplicas || 1} onChange={(e) => handleInputChange('minReplicas', e.target.value)} className="input-dark w-full text-sm" min="1" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Max Replicas</label>
                    <input type="number" value={formData.maxReplicas || 10} onChange={(e) => handleInputChange('maxReplicas', e.target.value)} className="input-dark w-full text-sm" min="1" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Target CPU Utilization (%)</label>
                    <input type="number" value={formData.targetCPUUtilization || 80} onChange={(e) => handleInputChange('targetCPUUtilization', e.target.value)} className="input-dark w-full text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Scale Target Kind</label>
                    <select value={formData.scaleTargetKind || 'Deployment'} onChange={(e) => handleInputChange('scaleTargetKind', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Deployment">Deployment</option>
                      <option value="StatefulSet">StatefulSet</option>
                      <option value="ReplicaSet">ReplicaSet</option>
                    </select>
                  </div>
                </div>
              )}
              {resourceType === 'storageclass' && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Provisioner</label>
                    <input type="text" value={formData.provisioner || 'kubernetes.io/gce-pd'} onChange={(e) => handleInputChange('provisioner', e.target.value)} className="input-dark w-full text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Reclaim Policy</label>
                    <select value={formData.reclaimPolicy || 'Delete'} onChange={(e) => handleInputChange('reclaimPolicy', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Delete">Delete</option>
                      <option value="Retain">Retain</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Volume Binding Mode</label>
                    <select value={formData.volumeBindingMode || 'Immediate'} onChange={(e) => handleInputChange('volumeBindingMode', e.target.value)} className="input-dark w-full text-sm">
                      <option value="Immediate">Immediate</option>
                      <option value="WaitForFirstConsumer">WaitForFirstConsumer</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Allow Volume Expansion</label>
                    <select value={formData.allowVolumeExpansion !== 'false' ? 'true' : 'false'} onChange={(e) => handleInputChange('allowVolumeExpansion', e.target.value)} className="input-dark w-full text-sm">
                      <option value="true">True</option>
                      <option value="false">False</option>
                    </select>
                  </div>
                </div>
              )}
              {(resourceType === 'role' || resourceType === 'clusterrole') && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-slate-300">Rules</label>
                    <button type="button" onClick={addRule} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Rule</button>
                  </div>
                  {rules.map((rule, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/50 rounded mb-2">
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <input type="text" value={rule.apiGroups} onChange={(e) => handleRuleChange(idx, 'apiGroups', e.target.value)} className="input-dark w-full text-sm" placeholder="API Groups" />
                        <input type="text" value={rule.resources} onChange={(e) => handleRuleChange(idx, 'resources', e.target.value)} className="input-dark w-full text-sm" placeholder="Resources" />
                        <input type="text" value={rule.verbs} onChange={(e) => handleRuleChange(idx, 'verbs', e.target.value)} className="input-dark w-full text-sm" placeholder="Verbs (get,list,create,delete)" />
                        <input type="text" value={rule.nonResourceURLs} onChange={(e) => handleRuleChange(idx, 'nonResourceURLs', e.target.value)} className="input-dark w-full text-sm" placeholder="Non-Resource URLs" />
                      </div>
                      <div className="flex justify-end">
                        <button type="button" onClick={() => removeRule(idx)} className="text-red-400 hover:text-red-300 text-sm">Remove Rule</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {(resourceType === 'rolebinding' || resourceType === 'clusterrolebinding') && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Role Reference</label>
                    <div className="grid grid-cols-3 gap-2">
                      <input type="text" value={roleRef.apiGroup} onChange={(e) => handleRoleRefChange('apiGroup', e.target.value)} className="input-dark w-full text-sm" placeholder="API Group" />
                      <select value={roleRef.kind} onChange={(e) => handleRoleRefChange('kind', e.target.value)} className="input-dark w-full text-sm">
                        <option value="Role">Role</option>
                        <option value="ClusterRole">ClusterRole</option>
                      </select>
                      <input type="text" value={roleRef.name} onChange={(e) => handleRoleRefChange('name', e.target.value)} className="input-dark w-full text-sm" placeholder="Role Name *" />
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-sm font-medium text-slate-300">Subjects</label>
                      <button type="button" onClick={addSubject} className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1"><PlusIcon className="h-4 w-4" /> Add Subject</button>
                    </div>
                    {subjects.map((subject, idx) => (
                      <div key={idx} className="p-3 bg-slate-800/50 rounded mb-2">
                        <div className="grid grid-cols-3 gap-2 mb-2">
                          <select value={subject.kind} onChange={(e) => handleSubjectChange(idx, 'kind', e.target.value)} className="input-dark w-full text-sm">
                            <option value="ServiceAccount">ServiceAccount</option>
                            <option value="User">User</option>
                            <option value="Group">Group</option>
                          </select>
                          <input type="text" value={subject.name} onChange={(e) => handleSubjectChange(idx, 'name', e.target.value)} className="input-dark w-full text-sm" placeholder="Name *" />
                          <input type="text" value={subject.namespace} onChange={(e) => handleSubjectChange(idx, 'namespace', e.target.value)} className="input-dark w-full text-sm" placeholder="Namespace" />
                        </div>
                        <div className="flex justify-end">
                          <button type="button" onClick={() => removeSubject(idx)} className="text-red-400 hover:text-red-300 text-sm">Remove Subject</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {resourceType === 'serviceaccount' && (
                <div>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={formData.automountToken !== false} onChange={(e) => handleInputChange('automountToken', e.target.checked)} className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500" />
                    <span className="text-sm font-medium text-slate-300">Automount Service Account Token</span>
                  </label>
                  <p className="text-xs text-slate-400 mt-1">Default: true (checked)</p>
                </div>
              )}
            </div>
            <div className="border-t border-slate-700 px-6 py-4 bg-slate-800/30 rounded-b-lg flex justify-end gap-3 mt-4">
              <button type="button" onClick={onClose} className="px-4 py-2 text-slate-300 border border-slate-600 rounded hover:bg-slate-700/50 transition-colors">Cancel</button>
              <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-600 transition-colors">
                {saving ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
