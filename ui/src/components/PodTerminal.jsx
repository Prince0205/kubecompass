/**
 * PodTerminal Component
 * Provides an interactive terminal session into a Kubernetes pod
 * Uses xterm.js for terminal rendering and WebSocket for communication
 */

import React, { useEffect, useRef, useCallback } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

export default function PodTerminal({ podName, namespace, container, shell = '/bin/sh' }) {
  const terminalRef = useRef(null)
  const xtermRef = useRef(null)
  const fitAddonRef = useRef(null)
  const wsRef = useRef(null)
  const isConnectedRef = useRef(false)

  const connect = useCallback(() => {
    if (!terminalRef.current || !podName) return

    // Clean up previous session
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (xtermRef.current) {
      xtermRef.current.dispose()
      xtermRef.current = null
    }

    // Create terminal instance
    const xterm = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontFamily: '"Cascadia Code", "Fira Code", "JetBrains Mono", Menlo, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.2,
      theme: {
        background: '#0f172a',
        foreground: '#e2e8f0',
        cursor: '#22d3ee',
        cursorAccent: '#0f172a',
        selectionBackground: '#334155',
        black: '#1e293b',
        red: '#f87171',
        green: '#4ade80',
        yellow: '#fbbf24',
        blue: '#60a5fa',
        magenta: '#c084fc',
        cyan: '#22d3ee',
        white: '#e2e8f0',
        brightBlack: '#475569',
        brightRed: '#fca5a5',
        brightGreen: '#86efac',
        brightYellow: '#fde68a',
        brightBlue: '#93c5fd',
        brightMagenta: '#d8b4fe',
        brightBrightCyan: '#67e8f9',
        brightWhite: '#f8fafc',
      },
      scrollback: 5000,
      allowTransparency: true,
    })

    const fitAddon = new FitAddon()
    xterm.loadAddon(fitAddon)

    xterm.open(terminalRef.current)
    fitAddon.fit()

    xtermRef.current = xterm
    fitAddonRef.current = fitAddon

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const containerParam = container ? `&container=${encodeURIComponent(container)}` : ''
    const shellParam = shell ? `&shell=${encodeURIComponent(shell)}` : ''
    const wsUrl = `${protocol}//${window.location.host}/api/resources/pods/${encodeURIComponent(podName)}/exec?${containerParam}${shellParam}`

    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws
    isConnectedRef.current = false

    ws.onopen = () => {
      isConnectedRef.current = true
      xterm.focus()
    }

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const uint8 = new Uint8Array(event.data)
        xterm.write(uint8)
      } else {
        xterm.write(event.data)
      }
    }

    ws.onclose = () => {
      isConnectedRef.current = false
      xterm.write('\r\n\x1b[31mConnection closed.\x1b[0m\r\n')
    }

    ws.onerror = () => {
      isConnectedRef.current = false
      xterm.write('\r\n\x1b[31mConnection error.\x1b[0m\r\n')
    }

    // Send terminal input to WebSocket
    xterm.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data))
      }
    })

    // Handle resize
    const handleResize = () => {
      if (fitAddonRef.current && xtermRef.current) {
        try {
          fitAddonRef.current.fit()
        } catch (e) {
          // Ignore resize errors during unmount
        }
      }
    }

    window.addEventListener('resize', handleResize)

    // Use ResizeObserver for container resize
    const resizeObserver = new ResizeObserver(() => {
      handleResize()
    })
    if (terminalRef.current) {
      resizeObserver.observe(terminalRef.current)
    }

    return () => {
      window.removeEventListener('resize', handleResize)
      resizeObserver.disconnect()
    }
  }, [podName, container, shell])

  useEffect(() => {
    const cleanup = connect()
    return () => {
      if (cleanup) cleanup()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (xtermRef.current) {
        xtermRef.current.dispose()
        xtermRef.current = null
      }
    }
  }, [connect])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnectedRef.current ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-xs text-slate-400 font-mono">
            {container || 'default'} → {shell}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (xtermRef.current) {
                xtermRef.current.clear()
              }
              connect()
            }}
            className="px-2 py-1 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded"
          >
            Reconnect
          </button>
        </div>
      </div>
      <div
        ref={terminalRef}
        className="flex-1 min-h-0 p-1"
        style={{ background: '#0f172a' }}
      />
    </div>
  )
}
