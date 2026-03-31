/**
 * AI Assistant Page
 * Natural language Kubernetes operations with dry-run and safety features
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useAppContext } from '../context/AppContext'
import { aiAPI } from '../api'
import {
  PaperAirplaneIcon,
  PlayIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  SparklesIcon,
  CommandLineIcon,
  CpuChipIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'

const RISK_COLORS = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#ef4444',
  unknown: '#6b7280',
}

const SUGGESTIONS = [
  'Scale deployment nginx to 3 replicas',
  'List all pods',
  'Show logs for my-pod',
  'Restart deployment my-app',
  'List all services',
  'Show resource usage',
  'Get events',
  'Describe pod my-pod',
  'Show all resources',
  'List nodes',
]

function ChatMessage({ message, onExecute, onDryRun }) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] bg-blue-600 rounded-2xl rounded-br-md px-4 py-3">
          <p className="text-sm text-white">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[85%]">
        <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-md px-4 py-3">
          {/* Description */}
          <p className="text-sm text-slate-200 mb-2">{message.content}</p>

          {/* Explanation from LLM */}
          {message.explanation && message.explanation !== message.content && (
            <p className="text-xs text-slate-400 mb-2 italic">{message.explanation}</p>
          )}

          {/* Command */}
          {message.command && (
            <div className="bg-slate-900 rounded-lg p-3 mb-3 border border-slate-700">
              <div className="flex items-center gap-2 mb-1">
                <CommandLineIcon className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-xs font-semibold text-cyan-400">Command</span>
                {message.source === 'llm' && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/20 text-purple-300 rounded">
                    AI
                  </span>
                )}
                {message.risk_level && (
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded"
                    style={{
                      color: RISK_COLORS[message.risk_level],
                      backgroundColor: `${RISK_COLORS[message.risk_level]}15`,
                    }}
                  >
                    {message.risk_level} risk
                  </span>
                )}
              </div>
              <code className="text-xs text-slate-200 font-mono block whitespace-pre-wrap break-all">
                {message.command}
              </code>
            </div>
          )}

          {/* Execution Result */}
          {message.result && (
            <div className={`rounded-lg p-3 mb-3 border ${
              message.result.success
                ? 'bg-green-900/20 border-green-700/50'
                : 'bg-red-900/20 border-red-700/50'
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                {message.result.success ? (
                  <CheckCircleIcon className="h-4 w-4 text-green-400" />
                ) : (
                  <XCircleIcon className="h-4 w-4 text-red-400" />
                )}
                <span className={`text-xs font-semibold ${message.result.success ? 'text-green-400' : 'text-red-400'}`}>
                  {message.result.success ? 'Success' : 'Failed'}
                </span>
              </div>
              {message.result.stdout && (
                <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap overflow-auto max-h-[200px] mt-1">
                  {message.result.stdout}
                </pre>
              )}
              {message.result.stderr && (
                <pre className="text-xs text-red-300 font-mono whitespace-pre-wrap overflow-auto max-h-[100px] mt-1">
                  {message.result.stderr}
                </pre>
              )}
            </div>
          )}

          {/* Action Buttons */}
          {message.command && !message.result && (
            <div className="flex gap-2 mt-2">
              <button
                onClick={() => onDryRun(message)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs text-slate-300 transition-colors"
              >
                <ShieldCheckIcon className="h-3.5 w-3.5" />
                Dry Run
              </button>
              <button
                onClick={() => onExecute(message)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-xs text-white transition-colors"
              >
                <PlayIcon className="h-3.5 w-3.5" />
                Execute
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function AIAssistant() {
  const { activeCluster } = useAppContext()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [aiStatus, setAiStatus] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    aiAPI.getStatus()
      .then(r => setAiStatus(r.data))
      .catch(() => setAiStatus({ llm_configured: false, rule_based: true, status: 'ready' }))
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return
    setInput('')

    const userMsg = { role: 'user', content: msg, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await aiAPI.chat(msg)
      const data = res.data
      const assistantMsg = {
        role: 'assistant',
        content: data.response,
        command: data.command,
        dry_run_command: data.dry_run_command,
        explanation: data.explanation,
        risk_level: data.risk_level,
        source: data.source,
        id: Date.now() + 1,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: err.response?.data?.detail || 'Failed to process your request. Please try again.',
        id: Date.now() + 1,
      }])
    } finally {
      setLoading(false)
    }
  }, [input, loading])

  const handleExecute = useCallback(async (message, dryRun = false) => {
    const cmd = dryRun && message.dry_run_command ? message.dry_run_command : message.command

    setMessages(prev => prev.map(m =>
      m.id === message.id ? { ...m, executing: true } : m
    ))

    try {
      const res = await aiAPI.execute(cmd, dryRun, message.dry_run_command)
      setMessages(prev => prev.map(m =>
        m.id === message.id ? { ...m, result: res.data, executing: false } : m
      ))
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === message.id ? {
          ...m,
          result: {
            success: false,
            stdout: '',
            stderr: err.response?.data?.detail || 'Execution failed',
            exit_code: -1,
          },
          executing: false,
        } : m
      ))
    }
  }, [])

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">AI Assistant</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <SparklesIcon className="h-8 w-8 text-cyan-400" />
            AI Assistant
          </h1>
          <p className="text-slate-400 mt-1">Natural language Kubernetes operations</p>
        </div>
        {aiStatus && (
          <div className="flex items-center gap-2 text-xs">
            {aiStatus.llm_configured ? (
              <span className="flex items-center gap-1 px-2.5 py-1 bg-purple-500/15 text-purple-300 rounded-full border border-purple-500/30">
                <CpuChipIcon className="h-3.5 w-3.5" />
                {aiStatus.llm_model || 'LLM'}
              </span>
            ) : (
              <span className="flex items-center gap-1 px-2.5 py-1 bg-slate-700 text-slate-400 rounded-full border border-slate-600">
                <CommandLineIcon className="h-3.5 w-3.5" />
                Rule-based
              </span>
            )}
          </div>
        )}
      </div>

      {/* Chat Area */}
      <div className="flex-1 glass-card overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-5">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <SparklesIcon className="h-16 w-16 text-slate-600 mb-4" />
              <h3 className="text-lg font-medium text-slate-300 mb-2">
                Describe what you want to do
              </h3>
              <p className="text-sm text-slate-500 mb-6 max-w-md">
                Tell me what you need in plain English. I'll generate the kubectl command
                and let you review it before executing.
              </p>

              <div className="w-full max-w-lg">
                <p className="text-xs text-slate-500 mb-2 text-left">Try these:</p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(s)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs text-slate-300 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map(msg => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onExecute={(m) => handleExecute(m, false)}
              onDryRun={(m) => handleExecute(m, true)}
            />
          ))}

          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-500 border-t-transparent" />
                  <span className="text-sm text-slate-400">Thinking...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-700 p-4 flex-shrink-0">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Describe what you want to do..."
              disabled={loading}
              className="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-cyan-500 focus:border-transparent disabled:opacity-50"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="px-4 py-3 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-xl hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 transition-all"
            >
              <PaperAirplaneIcon className="h-5 w-5" />
            </button>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <InformationCircleIcon className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-[11px] text-slate-500">
              All commands require your approval before execution. Use "Dry Run" to test safely.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
