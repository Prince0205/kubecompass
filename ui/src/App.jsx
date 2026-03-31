import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { AppProvider, useAppContext } from './context/AppContext'
import Header from './components/Header'
import SidebarNew from './components/SidebarNew'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Namespaces from './pages/Namespaces'
import Clusters from './pages/Clusters'
import Approvals from './pages/Approvals'
import Editor from './pages/Editor'
import Resources from './pages/Resources'
import RBACResources from './pages/RBACResources'
import Nodes from './pages/Nodes'
import Security from './pages/Security'
import History from './pages/History'
import CostAnalysis from './pages/CostAnalysis'
import Topology from './pages/Topology'
import Compare from './pages/Compare'
import Helm from './pages/Helm'
import AIAssistant from './pages/AIAssistant'

function ProtectedLayout() {
  const { auth, authLoading } = useAppContext()

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)' }}>
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 mb-4"></div>
          <p className="text-slate-400 font-medium">Loading...</p>
        </div>
      </div>
    )
  }

  if (!auth) {
    return <Login />
  }

  const { initialized } = useAppContext()
  if (!initialized) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)' }}>
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 mb-4"></div>
          <p className="text-slate-400 font-medium">Loading cluster...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col" style={{ background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)' }}>
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <SidebarNew />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/metrics" element={<Dashboard />} />
            <Route path="/namespaces" element={<Namespaces />} />
            <Route path="/clusters" element={<Clusters />} />
            <Route path="/nodes" element={<Nodes />} />
            <Route path="/security" element={<Security />} />
            <Route path="/history" element={<History />} />
            <Route path="/cost" element={<CostAnalysis />} />
            <Route path="/topology" element={<Topology />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/helm" element={<Helm />} />
            <Route path="/ai" element={<AIAssistant />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/editor" element={<Editor />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/workload/*" element={<Resources />} />
            <Route path="/config/*" element={<Resources />} />
            <Route path="/network/*" element={<Resources />} />
            <Route path="/storage/*" element={<Resources />} />
            <Route path="/rbac/roles" element={<RBACResources />} />
            <Route path="/rbac/clusterroles" element={<RBACResources />} />
            <Route path="/rbac/rolebindings" element={<RBACResources />} />
            <Route path="/rbac/clusterrolebindings" element={<RBACResources />} />
            <Route path="/rbac/serviceaccounts" element={<RBACResources />} />
            <Route path="/crds" element={<Resources />} />
            <Route path="/crds/:plural" element={<Resources />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <Router>
        <ProtectedLayout />
      </Router>
    </AppProvider>
  )
}