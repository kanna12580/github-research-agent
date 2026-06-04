import type { SSEvent } from '../hooks/useSSE'

interface RankingItem {
  rank: number
  full_name: string
  weighted_score?: number
  average_score?: number
  recommendation?: string
  dimension_scores?: Record<string, number>
}

interface GitHubComparison {
  recommended_repository?: string | null
  summary?: string
  ranking?: RankingItem[]
}

interface GitHubResearchSummaryProps {
  query: string
  events: SSEvent[]
  report: string
  streaming?: boolean
}

const GITHUB_URL_RE = /https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?\/?/g

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function extractGithubUrls(text: string): string[] {
  const urls = text.match(GITHUB_URL_RE) || []
  return Array.from(new Set(urls.map(url => url.replace(/\/$/, '').replace(/\.git$/, ''))))
}

function parseComparisonFromEvents(events: SSEvent[]): GitHubComparison | null {
  for (const event of [...events].reverse()) {
    const comparison = event.data.github_comparison
    if (!isRecord(comparison)) {
      continue
    }
    return {
      recommended_repository: typeof comparison.recommended_repository === 'string'
        ? comparison.recommended_repository
        : null,
      summary: typeof comparison.summary === 'string' ? comparison.summary : '',
      ranking: Array.isArray(comparison.ranking)
        ? comparison.ranking.filter(isRecord).map(item => ({
            rank: Number(item.rank) || 0,
            full_name: String(item.full_name || ''),
            weighted_score: Number(item.weighted_score) || undefined,
            average_score: Number(item.average_score) || undefined,
            recommendation: typeof item.recommendation === 'string' ? item.recommendation : undefined,
            dimension_scores: isRecord(item.dimension_scores)
              ? Object.fromEntries(Object.entries(item.dimension_scores).map(([key, value]) => [key, Number(value) || 0]))
              : undefined,
          }))
        : [],
    }
  }
  return null
}

function parseRecommendationFromReport(report: string): string | null {
  const match = report.match(/Recommended repository:\s*([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)/)
  if (match) {
    return match[1]
  }
  const chineseMatch = report.match(/推荐(?:仓库|项目)[：:]\s*([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)/)
  return chineseMatch?.[1] || null
}

function formatScore(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '-'
  }
  return value.toFixed(2)
}

function dimensionScore(item: RankingItem, key: string): string {
  const value = item.dimension_scores?.[key]
  return typeof value === 'number' ? String(value) : '-'
}

function GitHubResearchSummary({
  query,
  events,
  report,
  streaming = false,
}: GitHubResearchSummaryProps) {
  const urls = extractGithubUrls(`${query}\n${report}`)
  const comparison = parseComparisonFromEvents(events)
  const ranking = comparison?.ranking || []
  const recommended = comparison?.recommended_repository || parseRecommendationFromReport(report)
  const githubToolEvents = events.filter(event => {
    const toolName = String(event.data.tool_name || event.data.tool || '')
    const agent = String(event.data.agent || '')
    return agent === 'github' || toolName.includes('github')
  })
  const comparisonEvent = events.find(event => event.data.github_comparison)

  if (urls.length === 0 && !comparison && !recommended) {
    return null
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-5 py-4 flex items-center justify-between border-b border-xmgray-100">
        <div>
          <h3 className="text-sm font-medium text-xmgray-800">GitHub 技术调研看板</h3>
          <p className="mt-1 text-xs text-xmgray-400">
            仓库证据、确定性评分和多仓库推荐会在这里汇总
          </p>
        </div>
        <span className="tag-orange text-[11px]">
          {comparisonEvent ? '已完成排序' : streaming ? '采集中' : '待排序'}
        </span>
      </div>

      <div className="p-5 space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl bg-xmgray-50 p-4">
            <p className="text-xs text-xmgray-400">识别仓库</p>
            <p className="mt-1 text-2xl font-semibold text-xmgray-900">{urls.length}</p>
          </div>
          <div className="rounded-2xl bg-xmgray-50 p-4">
            <p className="text-xs text-xmgray-400">GitHub 工具事件</p>
            <p className="mt-1 text-2xl font-semibold text-xmgray-900">{githubToolEvents.length}</p>
          </div>
          <div className="rounded-2xl bg-xm-50 p-4">
            <p className="text-xs text-xm-700">推荐仓库</p>
            <p className="mt-1 truncate text-sm font-semibold text-xmgray-900">
              {recommended || '等待排序'}
            </p>
          </div>
        </div>

        {urls.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-xmgray-500">仓库输入</p>
            <div className="flex flex-wrap gap-2">
              {urls.map(url => (
                <a
                  key={url}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="tag hover:bg-xmgray-100"
                >
                  {url.replace('https://github.com/', '')}
                </a>
              ))}
            </div>
          </div>
        )}

        {comparison?.summary && (
          <div className="rounded-2xl border border-xm-100 bg-xm-50/70 p-4 text-sm leading-6 text-xmgray-700">
            {comparison.summary}
          </div>
        )}

        {ranking.length > 0 && (
          <div className="overflow-x-auto rounded-2xl border border-xmgray-100">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-xmgray-50 text-xmgray-500">
                <tr>
                  <th className="px-3 py-2">排名</th>
                  <th className="px-3 py-2">仓库</th>
                  <th className="px-3 py-2">加权分</th>
                  <th className="px-3 py-2">可复现</th>
                  <th className="px-3 py-2">深度</th>
                  <th className="px-3 py-2">扩展性</th>
                  <th className="px-3 py-2">工程质量</th>
                  <th className="px-3 py-2">建议</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xmgray-100">
                {ranking.map(item => (
                  <tr key={item.full_name} className={item.rank === 1 ? 'bg-xm-50/40' : 'bg-white'}>
                    <td className="px-3 py-2 font-semibold text-xmgray-900">#{item.rank}</td>
                    <td className="px-3 py-2 font-medium text-xmgray-800">{item.full_name}</td>
                    <td className="px-3 py-2 text-xm-700">{formatScore(item.weighted_score)}</td>
                    <td className="px-3 py-2">{dimensionScore(item, 'reproducibility')}</td>
                    <td className="px-3 py-2">{dimensionScore(item, 'project_depth')}</td>
                    <td className="px-3 py-2">{dimensionScore(item, 'extensibility')}</td>
                    <td className="px-3 py-2">{dimensionScore(item, 'engineering_quality')}</td>
                    <td className="px-3 py-2 text-xmgray-600">{item.recommendation || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default GitHubResearchSummary
