/**
 * Security Scanner Page
 * Displays cluster security findings with scoring and categorized results
 */

import React, { useState, useCallback } from 'react'
import { useAppContext } from '../context/AppContext'
import { apiClient } from '../api'
import { jsPDF } from 'jspdf'
import {
  ShieldCheckIcon,
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ArrowDownTrayIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'

const SEVERITY_CONFIG = {
  critical: {
    label: 'Critical',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    icon: ShieldExclamationIcon,
    barColor: 'bg-red-500',
  },
  high: {
    label: 'High',
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    icon: ExclamationTriangleIcon,
    barColor: 'bg-orange-500',
  },
  medium: {
    label: 'Medium',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    icon: ExclamationCircleIcon,
    barColor: 'bg-yellow-500',
  },
  low: {
    label: 'Low',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    icon: InformationCircleIcon,
    barColor: 'bg-blue-500',
  },
  info: {
    label: 'Info',
    color: 'text-slate-400',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
    icon: InformationCircleIcon,
    barColor: 'bg-slate-500',
  },
}

function getScoreColor(score) {
  if (score >= 80) return 'text-green-400'
  if (score >= 60) return 'text-yellow-400'
  if (score >= 40) return 'text-orange-400'
  return 'text-red-400'
}

function getScoreRingColor(score) {
  if (score >= 80) return 'stroke-green-400'
  if (score >= 60) return 'stroke-yellow-400'
  if (score >= 40) return 'stroke-orange-400'
  return 'stroke-red-400'
}

function getScoreLabel(score) {
  if (score >= 90) return 'Excellent'
  if (score >= 80) return 'Good'
  if (score >= 60) return 'Fair'
  if (score >= 40) return 'Poor'
  return 'Critical'
}

function ScoreRing({ score }) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference
  const ringColor = getScoreRingColor(score)

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" className="-rotate-90">
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          strokeWidth="8"
          className="stroke-slate-700"
        />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`${ringColor} transition-all duration-1000 ease-out`}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`text-3xl font-bold ${getScoreColor(score)}`}>{score}</span>
        <span className="text-xs text-slate-400">{getScoreLabel(score)}</span>
      </div>
    </div>
  )
}

function FindingItem({ finding }) {
  const [expanded, setExpanded] = useState(false)
  const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info
  const SeverityIcon = config.icon

  return (
    <div className={`border rounded-lg ${config.border} ${config.bg} overflow-hidden`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-white/5 transition-colors"
      >
        <SeverityIcon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.color}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.color} border ${config.border}`}>
              {config.label}
            </span>
            <span className="text-xs text-slate-500">{finding.category}</span>
          </div>
          <h4 className="text-sm font-medium text-white mt-1">{finding.title}</h4>
          <p className="text-xs text-slate-400 mt-1 truncate">{finding.resource_kind}: {finding.resource}</p>
        </div>
        {expanded ? (
          <ChevronDownIcon className="h-5 w-5 text-slate-500 flex-shrink-0" />
        ) : (
          <ChevronRightIcon className="h-5 w-5 text-slate-500 flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50 pt-3">
          <div>
            <h5 className="text-xs font-medium text-slate-300 mb-1">Description</h5>
            <p className="text-sm text-slate-400">{finding.description}</p>
          </div>
          <div>
            <h5 className="text-xs font-medium text-slate-300 mb-1">Recommendation</h5>
            <p className="text-sm text-cyan-400">{finding.recommendation}</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span>Resource: <span className="text-slate-300 font-mono">{finding.resource}</span></span>
            {finding.namespace && <span>Namespace: <span className="text-slate-300">{finding.namespace}</span></span>}
            <span>Kind: <span className="text-slate-300">{finding.resource_kind}</span></span>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Security() {
  const { activeCluster, activeNamespace } = useAppContext()
  const [scanResult, setScanResult] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState(null)
  const [filterSeverity, setFilterSeverity] = useState('all')
  const [expandedCategories, setExpandedCategories] = useState({})

  const runScan = useCallback(async () => {
    setScanning(true)
    setError(null)
    setScanResult(null)
    try {
      const response = await apiClient.get('/api/security/scan', { withCredentials: true })
      setScanResult(response.data)
      // Expand all categories by default
      const categories = {}
      if (response.data?.findings) {
        for (const f of response.data.findings) {
          categories[f.category] = true
        }
      }
      setExpandedCategories(categories)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Scan failed')
    } finally {
      setScanning(false)
    }
  }, [])

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({ ...prev, [category]: !prev[category] }))
  }

  const downloadPDF = useCallback(() => {
    if (!scanResult) return

    const doc = new jsPDF()
    const pageWidth = doc.internal.pageSize.getWidth()
    const pageHeight = doc.internal.pageSize.getHeight()
    const margin = 15
    const contentWidth = pageWidth - margin * 2
    let y = margin

    const addPageIfNeeded = (height = 10) => {
      if (y + height > pageHeight - margin) {
        doc.addPage()
        y = margin
        return true
      }
      return false
    }

    const drawLine = (lineY) => {
      doc.setDrawColor(200, 200, 200)
      doc.line(margin, lineY, pageWidth - margin, lineY)
    }

    // Header
    doc.setFontSize(22)
    doc.setTextColor(15, 23, 42)
    doc.text('Security Scan Report', margin, y + 8)
    y += 14

    doc.setFontSize(10)
    doc.setTextColor(100, 116, 139)
    doc.text(`Generated: ${new Date().toLocaleString()}`, margin, y + 5)
    y += 6
    doc.text(`Namespace: ${scanResult.namespace === '_all' ? 'All Namespaces' : scanResult.namespace}`, margin, y + 5)
    y += 10

    drawLine(y)
    y += 8

    // Score section
    const scoreColor = scanResult.score >= 80 ? [34, 197, 94]
      : scanResult.score >= 60 ? [234, 179, 8]
      : scanResult.score >= 40 ? [249, 115, 22]
      : [239, 68, 68]

    doc.setFontSize(14)
    doc.setTextColor(15, 23, 42)
    doc.text('Security Score', margin, y + 6)
    y += 14

    // Score box
    doc.setFillColor(241, 245, 249)
    doc.roundedRect(margin, y, 60, 28, 3, 3, 'F')
    doc.setFontSize(26)
    doc.setTextColor(...scoreColor)
    doc.text(`${scanResult.score}`, margin + 10, y + 18)
    doc.setFontSize(9)
    doc.setTextColor(100, 116, 139)
    doc.text(getScoreLabel(scanResult.score), margin + 35, y + 18)
    y += 34

    // Summary
    doc.setFontSize(12)
    doc.setTextColor(15, 23, 42)
    doc.text('Summary', margin, y + 6)
    y += 12

    const severityEntries = [
      ['Critical', scanResult.summary.critical || 0, [239, 68, 68]],
      ['High', scanResult.summary.high || 0, [249, 115, 22]],
      ['Medium', scanResult.summary.medium || 0, [234, 179, 8]],
      ['Low', scanResult.summary.low || 0, [59, 130, 246]],
      ['Info', scanResult.summary.info || 0, [100, 116, 139]],
    ]

    doc.setFontSize(10)
    for (const [label, count, color] of severityEntries) {
      doc.setTextColor(...color)
      doc.text(`${label}:`, margin, y + 5)
      doc.setTextColor(15, 23, 42)
      doc.text(`${count}`, margin + 25, y + 5)
      y += 6
    }

    y += 4
    doc.setTextColor(100, 116, 139)
    doc.text(`Total findings: ${scanResult.total_findings}`, margin, y)
    y += 10

    drawLine(y)
    y += 8

    // Findings
    if (scanResult.findings && scanResult.findings.length > 0) {
      doc.setFontSize(14)
      doc.setTextColor(15, 23, 42)
      doc.text('Findings', margin, y + 6)
      y += 14

      // Group findings by category
      const categories = {}
      for (const f of scanResult.findings) {
        if (!categories[f.category]) categories[f.category] = []
        categories[f.category].push(f)
      }

      for (const [category, findings] of Object.entries(categories)) {
        addPageIfNeeded(16)

        doc.setFillColor(241, 245, 249)
        doc.roundedRect(margin, y, contentWidth, 8, 1, 1, 'F')
        doc.setFontSize(11)
        doc.setTextColor(15, 23, 42)
        doc.text(`${category} (${findings.length})`, margin + 3, y + 5.5)
        y += 12

        for (const finding of findings) {
          const severityColors = {
            critical: [239, 68, 68],
            high: [249, 115, 22],
            medium: [234, 179, 8],
            low: [59, 130, 246],
            info: [100, 116, 139],
          }
          const sevColor = severityColors[finding.severity] || [100, 116, 139]

          // Estimate height needed
          const descLines = doc.splitTextToSize(finding.description, contentWidth - 8)
          const recLines = doc.splitTextToSize(`Recommendation: ${finding.recommendation}`, contentWidth - 8)
          const findingHeight = 6 + descLines.length * 4.5 + recLines.length * 4.5 + 10

          addPageIfNeeded(findingHeight)

          // Severity badge
          doc.setFillColor(...sevColor)
        doc.roundedRect(margin, y, 18, 5, 1, 1, 'F')
          doc.setFontSize(7)
          doc.setTextColor(255, 255, 255)
          doc.text(finding.severity.toUpperCase(), margin + 2, y + 3.5)
          y += 7

          // Title
          doc.setFontSize(10)
          doc.setTextColor(15, 23, 42)
          doc.text(finding.title, margin, y + 4)
          y += 7

          // Resource info
          doc.setFontSize(8)
          doc.setTextColor(100, 116, 139)
          let resourceLine = `${finding.resource_kind}: ${finding.resource}`
          if (finding.namespace) resourceLine += `  |  Namespace: ${finding.namespace}`
          doc.text(resourceLine, margin, y + 3)
          y += 6

          // Description
          doc.setFontSize(8)
          doc.setTextColor(51, 65, 85)
          for (const line of descLines) {
            doc.text(line, margin + 2, y + 3)
            y += 4.5
          }

          // Recommendation
          doc.setTextColor(6, 182, 212)
          for (const line of recLines) {
            doc.text(line, margin + 2, y + 3)
            y += 4.5
          }

          y += 4
        }

        y += 4
      }
    }

    // Footer on each page
    const pageCount = doc.internal.getNumberOfPages()
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i)
      doc.setFontSize(8)
      doc.setTextColor(148, 163, 184)
      doc.text('KubeCompass Security Scanner Report', margin, pageHeight - 8)
      doc.text(`Page ${i} of ${pageCount}`, pageWidth - margin - 20, pageHeight - 8)
    }

    const dateStr = new Date().toISOString().slice(0, 10)
    doc.save(`security-report-${dateStr}.pdf`)
  }, [scanResult])

  const filteredFindings = scanResult?.findings?.filter(f =>
    filterSeverity === 'all' || f.severity === filterSeverity
  ) || []

  // Group findings by category
  const groupedFindings = {}
  for (const f of filteredFindings) {
    if (!groupedFindings[f.category]) groupedFindings[f.category] = []
    groupedFindings[f.category].push(f)
  }

  if (!activeCluster) {
    return (
      <div className="glass-card p-6">
        <h2 className="text-lg font-semibold text-white">Security Scanner</h2>
        <p className="text-slate-400 mt-2">Please select a cluster from the header.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Security Scanner</h1>
          <p className="text-slate-400 mt-2">
            Scan your cluster for security vulnerabilities and misconfigurations
          </p>
        </div>
        <div className="flex items-center gap-3">
          {scanResult && (
            <button
              onClick={downloadPDF}
              className="flex items-center gap-2 px-5 py-2.5 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-all font-medium border border-slate-600"
            >
              <ArrowDownTrayIcon className="h-5 w-5" />
              Download PDF
            </button>
          )}
          <button
            onClick={runScan}
            disabled={scanning}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg hover:from-blue-500 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
          {scanning ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              Scanning...
            </>
          ) : (
            <>
              <ShieldCheckIcon className="h-5 w-5" />
              Run Scan
            </>
          )}
        </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {scanning && !scanResult && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-500 mb-4"></div>
            <p className="text-slate-400 font-medium">Running security scan...</p>
            <p className="text-slate-500 text-sm mt-1">Analyzing pods, services, RBAC, and nodes</p>
          </div>
        </div>
      )}

      {!scanResult && !scanning && !error && (
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <ShieldCheckIcon className="h-16 w-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-300">No scan results yet</h3>
            <p className="text-slate-500 text-sm mt-1">Click "Run Scan" to analyze your cluster for security issues</p>
          </div>
        </div>
      )}

      {scanResult && (
        <>
          {/* Score and Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-card p-6 flex items-center gap-6">
              <ScoreRing score={scanResult.score} />
              <div>
                <h3 className="text-lg font-semibold text-white">Security Score</h3>
                <p className="text-sm text-slate-400 mt-1">
                  {scanResult.total_findings} finding{scanResult.total_findings !== 1 ? 's' : ''} detected
                </p>
                <p className="text-xs text-slate-500 mt-2">
                  Namespace: <span className="text-cyan-400">{scanResult.namespace === '_all' ? 'All Namespaces' : scanResult.namespace}</span>
                </p>
              </div>
            </div>

            <div className="glass-card p-6">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Findings by Severity</h3>
              <div className="space-y-3">
                {Object.entries(SEVERITY_CONFIG).map(([key, config]) => {
                  const count = scanResult.summary[key] || 0
                  const total = scanResult.total_findings || 1
                  const percentage = (count / total) * 100
                  return (
                    <div key={key} className="flex items-center gap-3">
                      <span className={`text-xs font-medium w-16 ${config.color}`}>{config.label}</span>
                      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${config.barColor} rounded-full transition-all duration-500`}
                          style={{ width: `${count > 0 ? Math.max(percentage, 5) : 0}%` }}
                        />
                      </div>
                      <span className={`text-sm font-medium w-8 text-right ${config.color}`}>{count}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setFilterSeverity('all')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                filterSeverity === 'all'
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/50 border border-transparent'
              }`}
            >
              All ({scanResult.total_findings})
            </button>
            {Object.entries(SEVERITY_CONFIG).map(([key, config]) => {
              const count = scanResult.summary[key] || 0
              if (count === 0) return null
              return (
                <button
                  key={key}
                  onClick={() => setFilterSeverity(key)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    filterSeverity === key
                      ? `${config.bg} ${config.color} border ${config.border}`
                      : 'text-slate-400 hover:text-white hover:bg-slate-700/50 border border-transparent'
                  }`}
                >
                  {config.label} ({count})
                </button>
              )
            })}
          </div>

          {/* Findings by Category */}
          {filteredFindings.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <CheckCircleIcon className="h-12 w-12 text-green-500 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-green-400">
                  {filterSeverity === 'all' ? 'No issues found' : `No ${filterSeverity} issues`}
                </h3>
                <p className="text-slate-500 text-sm mt-1">Your cluster looks good!</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedFindings).map(([category, findings]) => {
                const isExpanded = expandedCategories[category] !== false
                return (
                  <div key={category} className="glass-card overflow-hidden">
                    <button
                      onClick={() => toggleCategory(category)}
                      className="w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-slate-700/30 transition-colors"
                    >
                      {isExpanded ? (
                        <ChevronDownIcon className="h-4 w-4 text-slate-500" />
                      ) : (
                        <ChevronRightIcon className="h-4 w-4 text-slate-500" />
                      )}
                      <h3 className="text-sm font-semibold text-white flex-1">{category}</h3>
                      <span className="text-xs text-slate-500">{findings.length} finding{findings.length !== 1 ? 's' : ''}</span>
                    </button>

                    {isExpanded && (
                      <div className="px-5 pb-4 space-y-2">
                        {findings.map(finding => (
                          <FindingItem key={finding.id} finding={finding} />
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
