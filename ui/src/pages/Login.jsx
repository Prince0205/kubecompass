/**
 * Login Page
 * Kubernetes Compass - Unified Kubernetes Management Platform
 */

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppContext } from '../context/AppContext'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { setAuth } = useAppContext()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!username || !password) {
      setError('Please enter both username and password')
      return
    }

    setLoading(true)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: username, password }),
        credentials: 'include',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Login failed')
      }

      if (data.success) {
        setAuth(data.user)
        navigate('/')
      } else {
        setError(data.message || 'Login failed')
      }
    } catch (err) {
      setError(err.message || 'An error occurred')
      console.error('Auth error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen login-bg flex items-center justify-center p-4 relative overflow-hidden">
      <div className="animated-nodes">
        <div className="node-blob"></div>
        <div className="node-blob"></div>
        <div className="node-blob"></div>
      </div>

      <div className="w-full max-w-md relative z-10">
        <div className="glass-panel p-8">
          <div className="flex items-center gap-3 mb-8">
            <div className="relative w-12 h-12">
              <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-12 h-12">
                <circle cx="32" cy="32" r="28" stroke="url(#grad1)" strokeWidth="2.5" fill="none"/>
                <circle cx="32" cy="32" r="18" stroke="url(#grad1)" strokeWidth="1.5" fill="none" opacity="0.6"/>
                <defs>
                  <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#06B6D4" />
                    <stop offset="100%" stopColor="#2563EB" />
                  </linearGradient>
                </defs>
                <path d="M32 12 L35 28 L32 32 L29 28 Z" fill="#06B6D4"/>
                <path d="M32 52 L29 36 L32 32 L35 36 Z" fill="#2563EB"/>
                <circle cx="32" cy="32" r="6" fill="#0F172A" stroke="#06B6D4" strokeWidth="1.5"/>
                <text x="32" y="35" textAnchor="middle" fill="#06B6D4" fontSize="7" fontWeight="bold">K</text>
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-wide">KUBERNETES COMPASS</h1>
              <p className="text-xs text-slate-400">Unified Kubernetes Management Platform</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-red-400 text-sm font-medium">{error}</p>
              </div>
            )}

            <div>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                disabled={loading}
                className="input-dark w-full text-base"
                required
              />
            </div>

            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                disabled={loading}
                className="input-dark w-full text-base pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300 transition-colors"
              >
                {showPassword ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? 'Please wait...' : (
                <>
                  <span>LOGIN</span>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </>
              )}
            </button>
          </form>

          <div className="mt-8">
            <p className="text-xs text-slate-500 mb-3 text-center">Connect to</p>
            <div className="flex items-center justify-center gap-4">
              <div className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                  <span className="text-white text-xs font-bold">K</span>
                </div>
                <span className="text-[10px] text-slate-400">Vanilla K8s</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2L6.5 7v10l5.5 5 5.5-5V7L12 2zm0 2.5L15 7l-3 3-3-3 3-2.5zM7.5 8.5l3.5 3.5-3.5 3.5-3.5-3.5 3.5-3.5zm9 0l3.5 3.5-3.5 3.5-3.5-3.5 3.5-3.5z"/>
                  </svg>
                </div>
                <span className="text-[10px] text-slate-400">AWS</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <span className="text-[10px] text-slate-400">AKS</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" fill="#4285F4"/>
                    <path d="M12 6v12M6 12h12" stroke="white" strokeWidth="2"/>
                  </svg>
                </div>
                <span className="text-[10px] text-slate-400">GKE</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <div className="w-8 h-8 bg-red-600 rounded-full flex items-center justify-center">
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="white">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                  </svg>
                </div>
                <span className="text-[10px] text-slate-400">Openshift</span>
              </div>
            </div>
          </div>
        </div>

        <div className="text-center mt-6">
          <p className="text-xs text-slate-500">
            Version 2.31 | Tuesday, February 3, 2026 15:14:59 IST | © 2006 Cluster Navigator Inc.
          </p>
        </div>

        <div className="absolute bottom-4 right-4">
          <svg className="w-3 h-3 text-white/30" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l3 7h7l-5.5 5 2 7L12 16l-6.5 5 2-7L2 9h7l3-7z"/>
          </svg>
        </div>
      </div>
    </div>
  )
}