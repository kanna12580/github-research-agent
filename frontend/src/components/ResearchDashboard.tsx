/**
 * ResearchDashboard - Xiaomi-style research interface.
 *
 * Design: Xiaomi's "less is more" philosophy
 * - Large search input centered at top
 * - Clean white cards with subtle shadows
 * - Orange accent for active states
 * - Generous whitespace, minimal chrome
 * - Split layout: traces | report
 */

import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useSSE } from '../hooks/useSSE'
import type { SSEvent } from '../hooks/useSSE'
import AgentTrace from './AgentTrace'
import ToolTrace from './ToolTrace'
import ReportPreview from './ReportPreview'
import GitHubResearchSummary from './GitHubResearchSummary'

interface ResearchResult {
  session_id: string
  query: string
  status: string
  report: string | null
  citations: Array<{
    citation_id: string
    source_url: string
    source_title: string
    source_type: string
  }> | Record<string, unknown> | null
  used_citation_ids?: string[]
  used_citation_count?: number
  collected_citation_count?: number
  agent_trace: unknown[]
  tool_histories?: unknown[]
  created_at: string
  completed_at: string | null
}

interface ResearchSessionSummary {
  session_id: string
  query: string
  status: string
  created_at: string
  updated_at?: string | null
  completed_at?: string | null
  citation_count?: number
  used_citation_count?: number
  collected_citation_count?: number
  report_preview?: string | null
}

interface ResearchDashboardProps {
  onBack?: () => void
}

const HISTORY_STORAGE_KEY = 'github-research-agent:history'

const DEMO_GITHUB_URLS = [
  'https://github.com/wblxr408/DeepIntel',
  'https://github.com/PavithraNagineni/multi-agent-research-system',
  'https://github.com/tarun7r/deep-research-agent',
]

const buildGithubResearchPrompt = (urls: string[]): string => {
  if (urls.length === 1) {
    return `请对这个 GitHub 开源项目做技术调研报告，重点分析可复现性、架构与 Agent 工作流深度、技术栈广度、可扩展性、工程质量和风险：${urls[0]}`
  }
  return `请对以下 GitHub 开源项目做技术调研、对比排序，并推荐最适合作为简历/面试复刻项目的仓库：${urls.join(' ')}`
}

function readLocalHistory(): ResearchSessionSummary[] {
  try {
    const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeLocalHistory(items: ResearchSessionSummary[]) {
  try {
    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(items.slice(0, 20)))
  } catch {
    // localStorage is best-effort demo continuity; backend history remains authoritative.
  }
}

function mergeHistory(
  remoteHistory: ResearchSessionSummary[],
  localHistory: ResearchSessionSummary[],
): ResearchSessionSummary[] {
  const byId = new Map<string, ResearchSessionSummary>()
  for (const item of [...localHistory, ...remoteHistory]) {
    byId.set(item.session_id, { ...byId.get(item.session_id), ...item })
  }
  return Array.from(byId.values())
    .sort((a, b) => Date.parse(b.created_at || '') - Date.parse(a.created_at || ''))
    .slice(0, 20)
}

function formatHistoryTime(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusLabel(status: string): string {
  if (status === 'completed') return '已完成'
  if (status === 'running') return '运行中'
  if (status === 'failed') return '失败'
  if (status === 'pending' || status === 'pending_confirmation') return '待确认'
  return status || '未知'
}

function statusClass(status: string): string {
  if (status === 'completed') return 'bg-emerald-50 text-emerald-700 border-emerald-100'
  if (status === 'running') return 'bg-xm-50 text-xm-700 border-xm-100'
  if (status === 'failed') return 'bg-red-50 text-red-700 border-red-100'
  return 'bg-xmgray-50 text-xmgray-500 border-xmgray-100'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function restoredTraceToEvents(trace: unknown[]): SSEvent[] {
  return trace.filter(isRecord).map((item, index) => {
    const eventType = String(item.event_type || item.type || 'trace')
    const data: Record<string, unknown> = { ...item }
    delete data.event_type
    return {
      type: eventType,
      data,
      timestamp: typeof item.timestamp === 'string' ? item.timestamp : new Date().toISOString(),
      restored: true,
      id: `restored-${index}`,
    } as SSEvent & { restored: boolean; id: string }
  })
}

function restoredToolHistoriesToEvents(histories: unknown[]): SSEvent[] {
  const events: SSEvent[] = []
  histories.filter(isRecord).forEach((history, historyIndex) => {
    const agent = String(history.agent_type || history.agent || '')
    const calls = Array.isArray(history.tool_calls) ? history.tool_calls : []
    calls.filter(isRecord).forEach((call, callIndex) => {
      const callId = String(call.call_id || `restored-tool-${historyIndex}-${callIndex}`)
      const toolName = String(call.tool_name || call.tool || 'tool')
      const startedAt = typeof call.started_at === 'string' ? call.started_at : undefined
      const completedAt = typeof call.completed_at === 'string' ? call.completed_at : startedAt
      const baseData: Record<string, unknown> = {
        call_id: callId,
        agent,
        tool_name: toolName,
        args: isRecord(call.args) ? call.args : {},
        restored: true,
      }
      events.push({
        type: 'tool_start',
        data: baseData,
        timestamp: startedAt,
      })
      events.push({
        type: call.status === 'error' ? 'tool_error' : 'tool_complete',
        data: {
          ...baseData,
          status: call.status || 'success',
          duration_ms: call.duration_ms,
          result_summary: call.result_summary,
          error: call.error,
        },
        timestamp: completedAt,
      })
    })
  })
  return events
}

function extractGithubRepoNames(text: string): string[] {
  const matches = Array.from(text.matchAll(/github\.com\/([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)/g))
  return Array.from(new Set(matches.map(match => match[1].replace(/\.git$/, ''))))
}

function fallbackHistoryEvents(result?: ResearchResult): SSEvent[] {
  if (!result) return []
  const citations = Array.isArray(result.citations) ? result.citations : []
  const repoNames = extractGithubRepoNames(`${result.query}\n${result.report || ''}\n${
    citations.map(citation => citation.source_url).join('\n')
  }`)
  const timestamp = result.completed_at || result.created_at || new Date().toISOString()
  const events: SSEvent[] = []

  if (repoNames.length > 0) {
    events.push({
      type: 'agent_start',
      data: {
        agent: 'github',
        content: `从历史报告恢复：检测到 ${repoNames.length} 个 GitHub 仓库`,
        restored: true,
      },
      timestamp,
    })
    repoNames.forEach((repoName, index) => {
      const callId = `fallback-github-${index}`
      events.push({
        type: 'tool_start',
        data: {
          call_id: callId,
          agent: 'github',
          tool_name: 'github_repository_collect',
          args: { repository: repoName },
          restored: true,
        },
        timestamp,
      })
      events.push({
        type: 'tool_complete',
        data: {
          call_id: callId,
          agent: 'github',
          tool_name: 'github_repository_collect',
          status: 'success',
          result_summary: `历史报告包含 ${repoName} 的引用证据`,
          restored: true,
        },
        timestamp,
      })
    })
    events.push({
      type: 'agent_complete',
      data: {
        agent: 'github',
        content: 'GitHub 仓库证据已从历史报告和引用恢复',
        restored: true,
      },
      timestamp,
    })
  }

  if (result.report) {
    events.push({
      type: 'agent_complete',
      data: {
        agent: 'report',
        content: `历史报告已恢复：${result.report.length} 字符，${displayCitationCount(result)} 条报告引用`,
        restored: true,
      },
      timestamp,
    })
  }

  return events
}

function displayCitationCount(result?: ResearchResult): number {
  if (!result) return 0
  if (typeof result.used_citation_count === 'number' && result.used_citation_count > 0) {
    return result.used_citation_count
  }
  return Array.isArray(result.citations) ? result.citations.length : 0
}

function ResearchDashboard({ onBack }: ResearchDashboardProps) {
  const [query, setQuery] = useState('')
  const [ragGroup, setRagGroup] = useState('')
  const [allowWebAfterRagHit, setAllowWebAfterRagHit] = useState(false)
  const [outputLength, setOutputLength] = useState<'short' | 'medium' | 'long'>('medium')
  const [githubUrls, setGithubUrls] = useState('')
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle')
  const [localHistory, setLocalHistory] = useState<ResearchSessionSummary[]>(() => readLocalHistory())
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionStatus, setSessionStatus] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // SSE for real-time updates
  const { events, status: sseStatus, error: sseError, clearEvents } = useSSE(activeSessionId)

  const { data: remoteHistory = [] } = useQuery<ResearchSessionSummary[]>({
    queryKey: ['research-sessions'],
    queryFn: async () => {
      const res = await fetch('/api/v1/research/sessions?limit=20')
      if (!res.ok) throw new Error('Failed to fetch research sessions')
      return res.json()
    },
    refetchInterval: activeSessionId ? 5000 : 15000,
  })

  const historyItems = useMemo(
    () => mergeHistory(remoteHistory, localHistory),
    [remoteHistory, localHistory],
  )

  const upsertLocalHistory = useCallback((item: ResearchSessionSummary) => {
    setLocalHistory(prev => {
      const next = [
        item,
        ...prev.filter(existing => existing.session_id !== item.session_id),
      ].slice(0, 20)
      writeLocalHistory(next)
      return next
    })
  }, [])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Fetch research result
  const { data: result, refetch: refetchResult } = useQuery<ResearchResult>({
    queryKey: ['research', activeSessionId],
    queryFn: async () => {
      const res = await fetch(`/api/v1/research/${activeSessionId}`)
      if (!res.ok) throw new Error('Failed to fetch result')
      return res.json()
    },
    enabled: !!activeSessionId,
    refetchInterval: isStreaming ? 3000 : false,
  })

  // Start research mutation
  const startMutation = useMutation({
    mutationFn: async (q: string) => {
      const res = await fetch('/api/v1/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          allow_web_after_rag_hit: allowWebAfterRagHit,
          rag_group: ragGroup.trim() || null,
          output_length: outputLength,
        }),
      })
      if (!res.ok) throw new Error('Failed to start research')
      return res.json()
    },
    onSuccess: (data) => {
      setActiveSessionId(data.session_id)
      setIsStreaming(true)
      setSessionStatus(data.status)
      upsertLocalHistory({
        session_id: data.session_id,
        query: query.trim(),
        status: data.status,
        created_at: new Date().toISOString(),
        citation_count: 0,
        report_preview: null,
      })
      clearEvents()
    },
  })

  // Detect when streaming ends
  useEffect(() => {
    const doneEvent = events.find((e: SSEvent) => e.type === 'done' || e.type === 'workflow_error')
    if (doneEvent) {
      setIsStreaming(false)
      setSessionStatus(doneEvent.type === 'done' ? 'completed' : 'failed')
      refetchResult()
    }
  }, [events, refetchResult])

  useEffect(() => {
    if (sseStatus === 'error') {
      setIsStreaming(false)
    }
  }, [sseStatus])

  useEffect(() => {
    if (result?.status) {
      setSessionStatus(result.status)
      if (result.status !== 'running') {
        setIsStreaming(false)
      }
      upsertLocalHistory({
        session_id: result.session_id,
        query: result.query,
        status: result.status,
        created_at: result.created_at,
        completed_at: result.completed_at,
        citation_count: displayCitationCount(result),
        used_citation_count: result.used_citation_count || 0,
        collected_citation_count: result.collected_citation_count || (
          Array.isArray(result.citations) ? result.citations.length : 0
        ),
        report_preview: result.report ? result.report.slice(0, 240) : null,
      })
    }
  }, [result, upsertLocalHistory])

  const restoredEvents = useMemo(
    () => restoredTraceToEvents(Array.isArray(result?.agent_trace) ? result.agent_trace : []),
    [result?.agent_trace],
  )
  const restoredToolEvents = useMemo(
    () => restoredToolHistoriesToEvents(Array.isArray(result?.tool_histories) ? result.tool_histories : []),
    [result?.tool_histories],
  )
  const fallbackEvents = useMemo(
    () => restoredEvents.length === 0 && restoredToolEvents.length === 0
      ? fallbackHistoryEvents(result)
      : [],
    [restoredEvents.length, restoredToolEvents.length, result],
  )
  const hasLiveEvents = events.some((event: SSEvent) =>
    !['connected', 'disconnected'].includes(event.type)
  )
  const isRestoredCompletedSession = Boolean(result) && !isStreaming && result?.status !== 'running'
  const restoredDisplayEvents = [...restoredEvents, ...restoredToolEvents, ...fallbackEvents]
  const displayEvents = isRestoredCompletedSession
    ? restoredDisplayEvents
    : hasLiveEvents
      ? events
      : restoredDisplayEvents

  // Build report from streaming chunks
  const streamedReport = displayEvents
    .filter((e: SSEvent) => e.type === 'report_chunk')
    .map((e: SSEvent) => String(e.data.chunk || ''))
    .join('')

  // Collect stats from events
  const agentEvents = displayEvents.filter((e: SSEvent) =>
    ['agent_start', 'agent_complete', 'agent_end'].includes(e.type)
  )
  const toolEvents = displayEvents.filter((e: SSEvent) =>
    ['tool_start', 'tool_call', 'tool_complete', 'tool_result', 'tool_error'].includes(e.type)
  )

  // Latest DAG node status
  const dagNodeEvents = displayEvents.filter((e: SSEvent) => e.type === 'agent_start')
  const currentNode = dagNodeEvents.length > 0
    ? (dagNodeEvents[dagNodeEvents.length - 1].data as { agent?: string })?.agent || ''
    : ''

  const handleStart = useCallback(() => {
    if (query.trim().length < 5) return
    startMutation.mutate(query.trim())
  }, [query, startMutation, allowWebAfterRagHit, ragGroup, outputLength])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleStart()
    }
    if (e.key === 'Escape') {
      onBack?.()
    }
  }, [handleStart, onBack])

  const handleNewResearch = useCallback(() => {
    setActiveSessionId(null)
    setQuery('')
    setGithubUrls('')
    setCopyStatus('idle')
    setRagGroup('')
    setSessionStatus(null)
    clearEvents()
    inputRef.current?.focus()
  }, [clearEvents])

  const handleBuildGithubQuery = useCallback(() => {
    const urls = githubUrls
      .split(/\s+/)
      .map(item => item.trim())
      .filter(Boolean)
    if (urls.length === 0) return
    setQuery(buildGithubResearchPrompt(urls))
    setOutputLength(urls.length > 1 ? 'long' : 'medium')
  }, [githubUrls])

  const handleUseDemoUrls = useCallback(() => {
    setGithubUrls(DEMO_GITHUB_URLS.join('\n'))
    setCopyStatus('idle')
  }, [])

  const handleCopyDemoPrompt = useCallback(async () => {
    const prompt = buildGithubResearchPrompt(DEMO_GITHUB_URLS)
    setQuery(prompt)
    setGithubUrls(DEMO_GITHUB_URLS.join('\n'))
    setOutputLength('long')
    try {
      await navigator.clipboard.writeText(prompt)
      setCopyStatus('copied')
    } catch {
      setCopyStatus('failed')
    }
  }, [])

  const handleRestoreSession = useCallback((item: ResearchSessionSummary) => {
    setActiveSessionId(item.session_id)
    setQuery(item.query)
    setSessionStatus(item.status)
    setIsStreaming(item.status === 'running' || item.status === 'pending')
    clearEvents()
  }, [clearEvents])

  const displayReport = streamedReport || result?.report || ''
  const normalizedCitations = Array.isArray(result?.citations) ? result.citations : []
  const usedCitationIds = Array.isArray(result?.used_citation_ids) ? result.used_citation_ids : []
  const reportCitations = usedCitationIds.length > 0
    ? normalizedCitations.filter(c => usedCitationIds.includes(c.citation_id))
    : normalizedCitations
  const showConfirmationState = sessionStatus === 'pending_confirmation'
  const hasVisibleEvents = events.some((event: SSEvent) => event.type !== 'connected')
  const isConnectingStream = isStreaming && (sseStatus === 'connecting' || sseStatus === 'connected') && !hasVisibleEvents
  const canRefetchResult = Boolean(activeSessionId)
  const workflowErrorEvent = [...displayEvents].reverse().find((event: SSEvent) => event.type === 'workflow_error')
  const isFailed = sessionStatus === 'failed'
  const workflowErrorText = String(workflowErrorEvent?.data.error || workflowErrorEvent?.data.message || '')
  const isGithubTokenLikelyMissing = /github|rate limit|permission|403|api/i.test(workflowErrorText)
  const emptyReportTitle = isConnectingStream
    ? '正在建立研究流连接...'
    : isFailed
      ? isGithubTokenLikelyMissing ? 'GitHub 采集失败' : '研究执行失败'
      : sseError
      ? '实时流已中断'
      : '报告暂未生成'
  const emptyReportDescription = isConnectingStream
    ? '任务已提交，正在等待首个 Agent 事件和报告片段。'
    : isFailed
      ? isGithubTokenLikelyMissing
        ? `GitHub API 可能触发限流或权限错误。请在 .env 中配置 GITHUB_TOKEN，然后执行 docker compose up -d --force-recreate api。原始错误：${workflowErrorText || '未知错误'}`
        : String(workflowErrorEvent?.data.error || workflowErrorEvent?.data.message || '任务执行过程中发生错误。')
      : sseError
      ? '实时事件连接失败，但仍可继续读取已落库的研究结果。'
      : '当前任务尚未返回可展示的报告内容。'

  // ======= RENDER =======

  // Full-screen research mode
  if (!activeSessionId) {
    return (
      <div className="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6">
        {/* Back button */}
        {onBack && (
          <button
            onClick={onBack}
            className="absolute top-20 left-6 btn-ghost"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 12L6 8L10 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            返回
          </button>
        )}

        {/* Hero text */}
        <div className="text-center mb-12 animate-fade-up">
          <h2 className="text-4xl md:text-5xl font-bold text-xmgray-900 tracking-tight">
            开始你的研究
          </h2>
          <p className="mt-3 text-base text-xmgray-400">
            输入研究主题，AI 将自动完成全流程研究
          </p>
        </div>

        {/* Search input - Xiaomi style large */}
        <div className="w-full max-w-2xl animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：分析 2025 年中国新能源汽车市场格局"
              className="input-xm pr-36 text-base"
              autoFocus
            />
            <button
              onClick={handleStart}
              disabled={isStreaming || query.trim().length < 5 || startMutation.isPending}
              className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary py-2.5 px-5"
            >
              {startMutation.isPending ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  启动中
                </>
              ) : (
                <>
                  研究
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M2 7H12M12 7L8 3M12 7L8 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </>
              )}
            </button>
          </div>
          <p className="mt-3 text-xs text-xmgray-400 text-center">
            默认先搜内部 RAG；内部没有结果时自动联网
          </p>
          <div className="mt-4 rounded-2xl border border-xm-100 bg-xm-50/60 p-4 text-left">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-xmgray-800">GitHub 开源项目调研</p>
                <p className="mt-1 text-xs text-xmgray-500">
                  粘贴一个或多个仓库 URL，自动生成技术调研、评分表和推荐排序。
                </p>
              </div>
              <span className="tag-orange shrink-0">Milestone 3</span>
            </div>
            <textarea
              value={githubUrls}
              onChange={e => setGithubUrls(e.target.value)}
              placeholder="https://github.com/wblxr408/DeepIntel&#10;https://github.com/tarun7r/deep-research-agent"
              className="mt-3 min-h-20 w-full rounded-xl border border-xm-100 bg-white px-3 py-2 text-sm text-xmgray-700 outline-none focus:border-xm-400"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleBuildGithubQuery}
                disabled={!githubUrls.trim()}
                className="btn-secondary py-2 text-xs"
              >
                生成 GitHub 调研任务
              </button>
              <button
                type="button"
                onClick={handleUseDemoUrls}
                className="tag hover:bg-white"
              >
                使用三项目对比示例
              </button>
              <button
                type="button"
                onClick={handleCopyDemoPrompt}
                className="tag hover:bg-white"
              >
                {copyStatus === 'copied'
                  ? '已复制 Demo prompt'
                  : copyStatus === 'failed'
                    ? '已填入，复制失败'
                    : '复制 Demo prompt'}
              </button>
            </div>
          </div>
          <div className="mt-4 rounded-2xl border border-xmgray-100 bg-white/80 p-4 text-left shadow-sm">
            <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
              <label className="block">
                <span className="text-xs font-medium text-xmgray-500">内部 RAG 分组（可选）</span>
                <input
                  type="text"
                  value={ragGroup}
                  onChange={e => setRagGroup(e.target.value)}
                  placeholder="例如：company_docs / project_a"
                  className="mt-1 w-full rounded-xl border border-xmgray-200 px-3 py-2 text-sm text-xmgray-700 outline-none focus:border-xm-400"
                />
              </label>
              <label className="flex items-center gap-2 rounded-xl bg-xmgray-50 px-3 py-2 text-xs text-xmgray-600">
                <input
                  type="checkbox"
                  checked={allowWebAfterRagHit}
                  onChange={e => setAllowWebAfterRagHit(e.target.checked)}
                  className="accent-orange-500"
                />
                内部命中后仍继续联网
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                { value: 'short', label: '短文' },
                { value: 'medium', label: '中篇' },
                { value: 'long', label: '长篇' },
              ].map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setOutputLength(option.value as 'short' | 'medium' | 'long')}
                  className={`rounded-full px-4 py-2 text-sm transition-colors ${
                    outputLength === option.value
                      ? 'bg-xm-500 text-white'
                      : 'bg-xmgray-50 text-xmgray-600 hover:bg-xmgray-100'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[11px] text-xmgray-400">
              不勾选时：内部 RAG 有结果就只用内部证据；内部为空才自动联网。
            </p>
          </div>
        </div>

        {historyItems.length > 0 && (
          <div className="mt-6 w-full max-w-2xl animate-fade-up" style={{ animationDelay: '0.2s' }}>
            <div className="rounded-2xl border border-xmgray-100 bg-white p-4 text-left shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-xmgray-800">最近研究</h3>
                  <p className="mt-1 text-xs text-xmgray-400">
                    可从本地缓存或后端历史中恢复报告，不需要重新调用 LLM。
                  </p>
                </div>
                <span className="tag text-[11px]">{historyItems.length} 条</span>
              </div>
              <div className="max-h-72 space-y-2 overflow-y-auto">
                {historyItems.map(item => (
                  <button
                    key={item.session_id}
                    type="button"
                    onClick={() => handleRestoreSession(item)}
                    className="w-full rounded-xl border border-xmgray-100 bg-xmgray-50/40 px-3 py-3 text-left transition-colors hover:border-xm-100 hover:bg-xm-50/50"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-xmgray-800">{item.query}</p>
                        <p className="mt-1 truncate text-xs text-xmgray-400">
                          {item.session_id} · {formatHistoryTime(item.completed_at || item.updated_at || item.created_at)}
                        </p>
                      </div>
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${statusClass(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </div>
                    {item.report_preview && (
                      <p className="mt-2 line-clamp-2 text-xs leading-5 text-xmgray-500">
                        {item.report_preview}
                      </p>
                    )}
                    <div className="mt-2 text-[11px] text-xmgray-400">
                      报告引用：{item.used_citation_count || item.citation_count || 0}
                      {item.collected_citation_count && item.collected_citation_count !== (item.used_citation_count || item.citation_count || 0)
                        ? ` / 采集来源：${item.collected_citation_count}`
                        : ''}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Example queries */}
        <div className="mt-10 flex flex-wrap justify-center gap-2 animate-fade-in" style={{ animationDelay: '0.3s' }}>
          {[
            '2025年AI Agent市场分析',
            '量子计算最新进展',
            '中国新能源汽车出口数据',
            '请对比 https://github.com/wblxr408/DeepIntel https://github.com/tarun7r/deep-research-agent 并推荐复刻优先级',
          ].map(q => (
            <button
              key={q}
              onClick={() => setQuery(q)}
              className="tag hover:bg-xmgray-100 cursor-pointer transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    )
  }

  // ======= ACTIVE RESEARCH MODE =======

  return (
      <div className="max-w-7xl mx-auto px-6 py-8">
      {showConfirmationState && (
        <div className="mb-6 rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          当前任务需要确认，尚未进入执行。
        </div>
      )}
      {sseError && (
        <div className="mb-6 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          SSE 连接异常：{sseError}
          {canRefetchResult && (
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="ml-3 text-red-800 underline underline-offset-2"
            >
              刷新页面
            </button>
          )}
        </div>
      )}
      {isConnectingStream && (
        <div className="mb-6 rounded-2xl border border-xm-100 bg-xm-50 px-4 py-3 text-sm text-xm-700">
          研究任务已启动，正在等待实时事件流连接完成。
        </div>
      )}
      {/* Top bar: query + stats */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <div className="flex items-center gap-4 min-w-0">
          {/* Back / New */}
          <button onClick={handleNewResearch} className="btn-ghost shrink-0">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 12L6 8L10 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            新研究
          </button>

          {/* Current query */}
          <div className="min-w-0">
            <p className="text-sm text-xmgray-400 truncate max-w-xl">{result?.query || query}</p>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 shrink-0">
          {/* Agent stats */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className={`status-dot ${isStreaming ? 'streaming' : 'online'}`} />
              <span className="text-xs text-xmgray-500">
                {isStreaming ? currentNode || '执行中' : isFailed ? '失败' : '已完成'}
              </span>
            </div>
            <div className="h-4 w-px bg-xmgray-200" />
            <span className="text-xs text-xmgray-400">{agentEvents.length} 步</span>
            <div className="h-4 w-px bg-xmgray-200" />
            <span className="text-xs text-xmgray-400">{toolEvents.length} 工具</span>
          </div>
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Traces panel */}
        <div className="lg:col-span-4 space-y-4">
          {/* Agent Trace - Xiaomi card */}
          <div className="card p-0 overflow-hidden">
            <div className="px-5 py-4 flex items-center justify-between border-b border-xmgray-100">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-md bg-xm-500/10 flex items-center justify-center">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M6 1.5L10 3.5V6.5L6 8.5L2 6.5V3.5L6 1.5Z" stroke="#ff8c00" strokeWidth="1.2" strokeLinejoin="round"/>
                  </svg>
                </div>
                <h3 className="text-sm font-medium text-xmgray-700">Agent 轨迹</h3>
              </div>
              <span className="tag text-[11px]">
                {isStreaming
                  ? <><span className="status-dot streaming mr-1" />运行中</>
                  : isFailed ? '失败' : '已完成'}
              </span>
            </div>
            <div className="p-4 h-[420px] overflow-y-auto">
              <AgentTrace events={displayEvents} />
            </div>
          </div>

          {/* Tool Trace */}
          <div className="card p-0 overflow-hidden">
            <div className="px-5 py-4 flex items-center justify-between border-b border-xmgray-100">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-md bg-emerald-500/10 flex items-center justify-center">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M2 6H10M10 6L7 3M10 6L7 9" stroke="#10b981" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <h3 className="text-sm font-medium text-xmgray-700">工具调用</h3>
              </div>
              <span className="text-xs text-xmgray-400">{toolEvents.length} 次</span>
            </div>
            <div className="p-4 h-44 overflow-y-auto">
              <ToolTrace events={displayEvents} />
            </div>
          </div>
        </div>

        {/* Right: Report panel */}
        <div className="lg:col-span-8 space-y-4">
          <GitHubResearchSummary
            query={result?.query || query}
            events={displayEvents}
            report={displayReport}
            streaming={isStreaming}
          />

          {/* Report */}
          <div className="card p-0 overflow-hidden">
            <div className="px-5 py-4 flex items-center justify-between border-b border-xmgray-100">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-md bg-xmgray-100 flex items-center justify-center">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <rect x="2" y="1.5" width="8" height="9" rx="1.5" stroke="#9e9e9e" strokeWidth="1.2"/>
                    <path d="M4 4H8M4 6H8M4 8H6" stroke="#9e9e9e" strokeWidth="1" strokeLinecap="round"/>
                  </svg>
                </div>
                <h3 className="text-sm font-medium text-xmgray-700">研究报告</h3>
              </div>
              <div className="flex items-center gap-3">
                {isStreaming && (
                  <span className="tag-orange text-[11px]">
                    <span className="status-dot streaming mr-1" />流式生成中
                  </span>
                )}
                {reportCitations.length > 0 && (
                  <span className="tag text-[11px]">
                    {displayCitationCount(result)} 条报告引用
                    {result?.collected_citation_count && result.collected_citation_count !== displayCitationCount(result)
                      ? ` / ${result.collected_citation_count} 条采集来源`
                      : ''}
                  </span>
                )}
              </div>
            </div>
            <div className="p-6 min-h-[500px] max-h-[680px] overflow-y-auto">
              <ReportPreview
                report={displayReport}
                citations={reportCitations}
                streaming={isStreaming}
                emptyTitle={emptyReportTitle}
                emptyDescription={emptyReportDescription}
              />
            </div>
          </div>

          {/* Citations panel */}
          {reportCitations.length > 0 && (
            <div className="card p-0 overflow-hidden">
              <div className="px-5 py-4 border-b border-xmgray-100">
                <h3 className="text-sm font-medium text-xmgray-700">
                  引用来源
                </h3>
                {result?.collected_citation_count && result.collected_citation_count !== reportCitations.length && (
                  <p className="mt-1 text-xs text-xmgray-400">
                    当前报告实际使用 {reportCitations.length} 条引用；本次工作流共采集 {result.collected_citation_count} 条来源。
                  </p>
                )}
              </div>
              <div className="p-5 max-h-52 overflow-y-auto space-y-2">
                {reportCitations.map((c, i) => (
                  <a
                    key={i}
                    href={c.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-xmgray-50 transition-colors group"
                  >
                    <span className="shrink-0 w-5 h-5 rounded bg-xmgray-100 text-[10px] font-medium text-xmgray-500 flex items-center justify-center mt-0.5 group-hover:bg-xm-100 group-hover:text-xm-700 transition-colors">
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm text-xmgray-700 group-hover:text-xm-700 transition-colors truncate">
                        {c.source_title || c.source_url}
                      </p>
                      <p className="text-xs text-xmgray-400 truncate mt-0.5">{c.source_url}</p>
                    </div>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="shrink-0 mt-1 text-xmgray-300 group-hover:text-xmgray-400 transition-colors">
                      <path d="M5 2H2V10H10V7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ResearchDashboard
