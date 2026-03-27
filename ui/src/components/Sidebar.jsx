import React from 'react'
import { ChevronRightIcon } from '@heroicons/react/24/solid'

export default function Sidebar({ onNavigate, selected }){
  const nav = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'clusters', label: 'Clusters' },
    { key: 'resources', label: 'Resources' },
    { key: 'editor', label: 'YAML Editor' }
  ]

  return (
    <div>
      <div className="mb-4 text-lg font-bold">Kubernetes Compass</div>
      <nav>
        <ul className="space-y-1">
          {nav.map(n => (
            <li key={n.key} className={`flex items-center justify-between px-3 py-2 rounded hover:bg-gray-100 cursor-pointer ${selected===n.key ? 'bg-blue-50 font-semibold' : ''}`} onClick={()=>onNavigate(n.key)}>
              <span>{n.label}</span>
              <ChevronRightIcon className="h-4 w-4 text-gray-400" />
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
