/**
 * ReportPreview - Xiaomi-style report rendering with Markdown and citations.
 */

import { useMemo, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface ReportPreviewProps {
  report: string
  citations: Array<{ citation_id: string; source_url: string; source_title: string }>
  streaming?: boolean
  emptyTitle?: string
  emptyDescription?: string
}

type ContentBlock =
  | { type: 'markdown'; content: string }
  | { type: 'table'; header: string[]; rows: string[][] }

function normalizeReferencesSection(markdown: string): string {
  const marker = markdown.match(/\n## References\b/)
  if (!marker || marker.index === undefined) {
    return markdown
  }
  const start = marker.index
  const before = markdown.slice(0, start)
  const references = markdown.slice(start)
  const normalized = references.replace(
    /(\[citation:\d+\])/g,
    (_match, citation, offset) => (offset === 0 ? citation : `\n${citation}`),
  )
  return `${before}${normalized.replace(/\n{3,}/g, '\n\n')}`
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)
}

function isTableRow(line: string): boolean {
  return /^\s*\|.*\|\s*$/.test(line)
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim())
}

function splitMarkdownTables(markdown: string): ContentBlock[] {
  const lines = markdown.split(/\r?\n/)
  const blocks: ContentBlock[] = []
  const markdownBuffer: string[] = []
  let index = 0

  const flushMarkdown = () => {
    const content = markdownBuffer.join('\n').trim()
    if (content) {
      blocks.push({ type: 'markdown', content })
    }
    markdownBuffer.length = 0
  }

  while (index < lines.length) {
    const current = lines[index]
    const next = lines[index + 1]

    if (isTableRow(current) && next && isTableSeparator(next)) {
      flushMarkdown()
      const header = parseTableRow(current)
      const rows: string[][] = []
      index += 2
      while (index < lines.length && isTableRow(lines[index])) {
        rows.push(parseTableRow(lines[index]))
        index += 1
      }
      blocks.push({ type: 'table', header, rows })
      continue
    }

    markdownBuffer.push(current)
    index += 1
  }

  flushMarkdown()
  return blocks
}

function ReportPreview({
  report,
  citations,
  streaming = false,
  emptyTitle,
  emptyDescription,
}: ReportPreviewProps) {
  const citationMap = useMemo(() => {
    const map = new Map<string, { url: string; title: string }>()
    citations.forEach(c => {
      map.set(c.citation_id, { url: c.source_url, title: c.source_title })
    })
    return map
  }, [citations])
  const normalizedReport = useMemo(() => normalizeReferencesSection(report), [report])
  const contentBlocks = useMemo(() => splitMarkdownTables(normalizedReport), [normalizedReport])

  if (!report) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center py-16">
        {streaming ? (
          <>
            <div className="relative w-10 h-10 mb-4">
              <div className="absolute inset-0 border-2 border-xm-200 rounded-full" />
              <div className="absolute inset-0 border-2 border-xm-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <p className="text-sm text-xmgray-500 font-medium">正在生成研究报告...</p>
            <p className="text-xs text-xmgray-400 mt-1">请稍候，AI 正在分析和撰写</p>
          </>
        ) : (
          <>
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" className="mb-4 text-xmgray-200">
              <rect x="6" y="4" width="28" height="32" rx="4" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M12 12H28M12 18H28M12 24H20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <p className="text-sm text-xmgray-500 font-medium">
              {emptyTitle || '输入研究主题后，报告将在此显示'}
            </p>
            {emptyDescription && (
              <p className="text-xs text-xmgray-400 mt-1">{emptyDescription}</p>
            )}
          </>
        )}
      </div>
    )
  }

  const markdownComponents = {
    // Links
    link: ({ href, children }: { href?: string; children?: ReactNode }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="citation-ref"
      >
        {children}
      </a>
    ),
    // Code blocks
    code: ({ className, children, ...props }: { className?: string; children?: ReactNode }) => {
      const match = /language-(\w+)/.exec(className || '')
      const isInline = !match
      return isInline ? (
        <code className={className} {...props}>
          {children}
        </code>
      ) : (
        <SyntaxHighlighter
          style={oneDark}
          language={match[1]}
          PreTag="div"
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      )
    },
    // Citation references
    text: ({ children }: { children?: ReactNode }) => {
      const text = String(children)
      const citationPattern = /\[citation:(\d+)\]/g
      if (!citationPattern.test(text)) return <>{children}</>

      const parts = text.split(/(\[citation:\d+\])/g)
      return (
        <>
          {parts.map((part, i) => {
            const match = part.match(/\[citation:(\d+)\]/)
            if (match) {
              const num = match[1]
              const citation = citationMap.get(`citation:${num}`)
              if (citation?.url) {
                return (
                  <a
                    key={i}
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="citation-ref text-xs align-super"
                    title={citation.title}
                  >
                    [{num}]
                  </a>
                )
              }
              return <span key={i} className="text-xm-600 text-xs align-super">[{num}]</span>
            }
            return <span key={i}>{part}</span>
          })}
        </>
      )
    },
  }

  return (
    <div className="report-content">
      {contentBlocks.map((block, blockIndex) => (
        block.type === 'table' ? (
          <div key={blockIndex} className="my-5 overflow-x-auto rounded-xl border border-xmgray-100">
            <table className="min-w-full divide-y divide-xmgray-100 text-sm">
              <thead className="bg-xmgray-50">
                <tr>
                  {block.header.map((cell, cellIndex) => (
                    <th key={cellIndex} className="px-3 py-2 text-left font-semibold text-xmgray-700">
                      <ReactMarkdown components={markdownComponents}>{cell}</ReactMarkdown>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-xmgray-100 bg-white">
                {block.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className={rowIndex === 0 ? 'bg-xm-50/60' : undefined}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="px-3 py-2 align-top text-xmgray-600">
                        <ReactMarkdown components={markdownComponents}>{cell}</ReactMarkdown>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <ReactMarkdown key={blockIndex} components={markdownComponents}>
            {block.content}
          </ReactMarkdown>
        )
      ))}
      {streaming && (
        <span className="inline-block w-1.5 h-4 bg-xm-500 ml-1 animate-pulse" />
      )}
    </div>
  )
}

export default ReportPreview
