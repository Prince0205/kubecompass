/**
 * Enhanced Sidebar Component with all Kubernetes resource types
 * Organized by category with full expansion and create buttons
 * Dynamically loads CRD names grouped by API group (OpenLens-style)
 */

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  SparklesIcon,
  CpuChipIcon,
  Cog6ToothIcon,
  GlobeAltIcon,
  Square3Stack3DIcon,
  CommandLineIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ServerStackIcon,
  ClipboardDocumentCheckIcon,
  KeyIcon,
  CubeIcon,
} from '@heroicons/react/24/outline'
import axios from 'axios'
import { useAppContext } from '../context/AppContext'

export default function Sidebar() {
  const location = useLocation()
  const { activeCluster } = useAppContext()
  const [expandedSections, setExpandedSections] = useState({
    dashboard: true,
    workload: true,
    config: true,
    network: true,
    storage: true,
    rbac: true,
    crds: true,
  })
  const [expandedGroups, setExpandedGroups] = useState({})
  const [crdItems, setCrdItems] = useState([])
  const [crdsLoading, setCrdsLoading] = useState(false)
  const lastClusterRef = useRef(null)

  // Direct fetch for CRDs - bypasses useFetchList to avoid timing issues
  const loadCRDs = useCallback(async () => {
    if (!activeCluster) {
      setCrdItems([])
      return
    }
    setCrdsLoading(true)
    try {
      const response = await axios.get('/api/resources/crds', { withCredentials: true })
      const crds = response.data?.crds || []
      console.log(`[Sidebar] Loaded ${crds.length} CRDs from API`)
      setCrdItems(crds)
    } catch (err) {
      console.error('Sidebar: Failed to load CRDs:', err?.response?.data?.detail || err.message)
      setCrdItems([])
    } finally {
      setCrdsLoading(false)
    }
  }, [activeCluster])

  // Fetch on mount and when cluster changes
  useEffect(() => {
    if (activeCluster && activeCluster !== lastClusterRef.current) {
      lastClusterRef.current = activeCluster
      loadCRDs()
    }
  }, [activeCluster, loadCRDs])

  // Group CRDs by API group (OpenLens-style)
  const crdGroups = useMemo(() => {
    const groups = {}
    for (const crd of crdItems) {
      const group = crd.group || 'unknown'
      if (!groups[group]) groups[group] = []
      groups[group].push(crd)
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [crdItems])

  const staticMenuSections = [
    {
      id: 'dashboard',
      label: 'Overview',
      icon: SparklesIcon,
      items: [
        { label: 'Dashboard', path: '/', icon: SparklesIcon },
        { label: 'Clusters', path: '/clusters', icon: ServerStackIcon, createType: 'cluster' },
        { label: 'Namespaces', path: '/namespaces', icon: SparklesIcon, createType: 'namespace' },
        { label: 'Nodes', path: '/nodes', icon: ServerStackIcon },
        { label: 'Approvals', path: '/approvals', icon: ClipboardDocumentCheckIcon },
        { label: 'Metrics', path: '/metrics', icon: CpuChipIcon },
      ],
    },
    {
      id: 'workload',
      label: 'Workloads',
      icon: CpuChipIcon,
      items: [
        { label: 'Pods', path: '/workload/pods', icon: CpuChipIcon, createType: 'pod' },
        { label: 'Deployments', path: '/workload/deployments', icon: CpuChipIcon, createType: 'deployment' },
        { label: 'ReplicaSets', path: '/workload/replicasets', icon: CpuChipIcon },
        { label: 'StatefulSets', path: '/workload/statefulsets', icon: CpuChipIcon, createType: 'statefulset' },
        { label: 'DaemonSets', path: '/workload/daemonsets', icon: CpuChipIcon, createType: 'daemonset' },
        { label: 'Jobs', path: '/workload/jobs', icon: CpuChipIcon, createType: 'job' },
        { label: 'CronJobs', path: '/workload/cronjobs', icon: CpuChipIcon, createType: 'cronjob' },
      ],
    },
    {
      id: 'config',
      label: 'Configuration',
      icon: Cog6ToothIcon,
      items: [
        { label: 'ConfigMaps', path: '/config/configmaps', icon: Cog6ToothIcon, createType: 'configmap' },
        { label: 'Secrets', path: '/config/secrets', icon: Cog6ToothIcon, createType: 'secret' },
        { label: 'HPAs', path: '/config/hpas', icon: Cog6ToothIcon, createType: 'hpa' },
        { label: 'Resource Quotas', path: '/config/quotas', icon: Cog6ToothIcon, createType: 'quota' },
        { label: 'Limit Ranges', path: '/config/limitranges', icon: Cog6ToothIcon, createType: 'limitrange' },
      ],
    },
    {
      id: 'network',
      label: 'Network',
      icon: GlobeAltIcon,
      items: [
        { label: 'Services', path: '/network/services', icon: GlobeAltIcon, createType: 'service' },
        { label: 'Endpoints', path: '/network/endpoints', icon: GlobeAltIcon },
        { label: 'Ingresses', path: '/network/ingresses', icon: GlobeAltIcon, createType: 'ingress' },
        { label: 'Network Policies', path: '/network/policies', icon: GlobeAltIcon, createType: 'networkpolicy' },
      ],
    },
    {
      id: 'storage',
      label: 'Storage',
      icon: Square3Stack3DIcon,
      items: [
        { label: 'Persistent Volumes', path: '/storage/pvs', icon: Square3Stack3DIcon, createType: 'pv' },
        { label: 'PVCs', path: '/storage/pvcs', icon: Square3Stack3DIcon, createType: 'pvc' },
        { label: 'Storage Classes', path: '/storage/classes', icon: Square3Stack3DIcon, createType: 'storageclass' },
      ],
    },
    {
      id: 'rbac',
      label: 'RBAC',
      icon: KeyIcon,
      items: [
        { label: 'Roles', path: '/rbac/roles', icon: KeyIcon, createType: 'role' },
        { label: 'ClusterRoles', path: '/rbac/clusterroles', icon: KeyIcon, createType: 'clusterrole', clusterScoped: true },
        { label: 'Role Bindings', path: '/rbac/rolebindings', icon: KeyIcon, createType: 'rolebinding' },
        { label: 'ClusterRole Bindings', path: '/rbac/clusterrolebindings', icon: KeyIcon, createType: 'clusterrolebinding', clusterScoped: true },
        { label: 'Service Accounts', path: '/rbac/serviceaccounts', icon: KeyIcon, createType: 'serviceaccount' },
      ],
    },
  ]

  const isActive = (path) => {
    if (location.pathname === path) return true
    if (path !== '/crds' && path !== '/' && location.pathname.startsWith(path)) return true
    return false
  }

  const toggleSection = (sectionId) => {
    setExpandedSections(prev => ({ ...prev, [sectionId]: !prev[sectionId] }))
  }

  const toggleGroup = (groupName) => {
    setExpandedGroups(prev => ({ ...prev, [groupName]: !prev[groupName] }))
  }

  const renderCRDSection = () => {
    const isExpanded = expandedSections.crds

    return (
      <div key="crds" className="space-y-1">
        <button
          onClick={() => toggleSection('crds')}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors"
        >
          <CommandLineIcon className="h-5 w-5 text-cyan-500" />
          <span className="flex-1 text-left">Custom Resources</span>
          {crdsLoading && (
            <div className="animate-spin rounded-full h-3 w-3 border border-slate-500 border-t-cyan-500" />
          )}
          {!crdsLoading && crdGroups.length > 0 && (
            <span className="text-xs text-slate-500 mr-1">
              {crdGroups.reduce((sum, [, items]) => sum + items.length, 0)}
            </span>
          )}
          {isExpanded ? (
            <ChevronDownIcon className="h-4 w-4 text-slate-500" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 text-slate-500" />
          )}
        </button>

        {isExpanded && (
          <div className="space-y-0.5 pl-4">
            <Link
              to="/crds"
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors ${
                isActive('/crds')
                  ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-400 font-semibold border-l-2 border-cyan-500'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/30'
              }`}
            >
              <CommandLineIcon className="h-4 w-4" />
              <span>All CRDs</span>
              {!crdsLoading && crdGroups.length > 0 && (
                <span className="text-xs text-slate-500 ml-auto">
                  {crdGroups.reduce((sum, [, items]) => sum + items.length, 0)}
                </span>
              )}
            </Link>

            {crdGroups.map(([group, crds]) => {
              const groupExpanded = expandedGroups[group] !== false
              return (
                <div key={group} className="space-y-0.5">
                  <button
                    onClick={() => toggleGroup(group)}
                    className="w-full flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-700/30 transition-colors"
                  >
                    {groupExpanded ? (
                      <ChevronDownIcon className="h-3 w-3 text-slate-500" />
                    ) : (
                      <ChevronRightIcon className="h-3 w-3 text-slate-500" />
                    )}
                    <span className="truncate flex-1 text-left">{group}</span>
                    <span className="text-slate-500">{crds.length}</span>
                  </button>

                  {groupExpanded && (
                    <div className="space-y-0.5 pl-4">
                      {crds.map((crd) => {
                        const crdPath = `/crds/${crd.plural}`
                        const active = isActive(crdPath)
                        return (
                          <Link
                            key={crd.plural}
                            to={crdPath}
                            state={{
                              crdMeta: {
                                name: crd.name,
                                group: crd.group,
                                kind: crd.kind,
                                plural: crd.plural,
                                scope: crd.scope,
                                versions: crd.versions,
                              }
                            }}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs transition-colors ${
                              active
                                ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-400 font-semibold border-l-2 border-cyan-500'
                                : 'text-slate-400 hover:text-white hover:bg-slate-700/30'
                            }`}
                          >
                            <CubeIcon className="h-3 w-3 flex-shrink-0" />
                            <span className="truncate">{crd.kind}</span>
                            {crd.scope === 'Cluster' && (
                              <span className="ml-auto text-[10px] text-purple-400 flex-shrink-0">C</span>
                            )}
                          </Link>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}

            {crdsLoading && (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-500">
                <div className="animate-spin rounded-full h-3 w-3 border border-slate-500 border-t-cyan-500" />
                Loading CRDs...
              </div>
            )}

            {!crdsLoading && !activeCluster && (
              <p className="px-3 py-2 text-xs text-slate-500 italic">Select a cluster</p>
            )}

            {!crdsLoading && activeCluster && crdGroups.length === 0 && (
              <p className="px-3 py-2 text-xs text-slate-500 italic">No CRDs found</p>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="h-screen w-72 overflow-y-auto border-r border-slate-700/50 bg-slate-800/30 flex flex-col">
      <div className="sticky top-0 border-b border-slate-700/50 bg-slate-800/50 px-4 py-4 z-10 backdrop-blur-sm">
        <h2 className="text-lg font-bold text-white">Menu</h2>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {staticMenuSections.map((section) => {
          const SectionIcon = section.icon
          const isExpanded = expandedSections[section.id]

          return (
            <div key={section.id} className="space-y-1">
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:bg-slate-700/50 hover:text-white transition-colors"
              >
                <SectionIcon className="h-5 w-5 text-cyan-500" />
                <span className="flex-1 text-left">{section.label}</span>
                {isExpanded ? (
                  <ChevronDownIcon className="h-4 w-4 text-slate-500" />
                ) : (
                  <ChevronRightIcon className="h-4 w-4 text-slate-500" />
                )}
              </button>

              {isExpanded && (
                <div className="space-y-0.5 pl-6">
                  {section.items.map((item) => {
                    const ItemIcon = item.icon
                    const active = isActive(item.path)
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
                          active
                            ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-400 font-semibold border-l-2 border-cyan-500'
                            : 'text-slate-400 hover:text-white hover:bg-slate-700/30'
                        }`}
                      >
                        <ItemIcon className="h-4 w-4" />
                        <span>{item.label}</span>
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        {renderCRDSection()}
      </nav>

      <div className="border-t border-slate-700/50 px-4 py-3 bg-slate-800/30 backdrop-blur-sm">
        <p className="text-xs text-slate-500">Ready to manage your Kubernetes resources</p>
      </div>
    </div>
  )
}
