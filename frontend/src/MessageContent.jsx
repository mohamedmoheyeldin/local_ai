import { useState } from 'react'
import { Button, ButtonGroup, Details } from '@primer/react'
import { CopyIcon, DownloadIcon } from '@primer/octicons-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'

function download(text, name, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url)
}

function CodeBlock({ className, children, ...props }) {
  const [copied, setCopied] = useState(false)
  const text = String(children).replace(/\n$/, '')
  const block = className?.includes('language-') || text.includes('\n')
  if (!block) return <code className={className} {...props}>{children}</code>
  const extension = className?.replace('language-', '') || 'txt'
  return <div className="code-block"><div className="code-block-toolbar"><ButtonGroup><Button size="small" variant="invisible" leadingVisual={CopyIcon} onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200) }}>{copied ? 'Copied' : 'Copy'}</Button><Button size="small" variant="invisible" leadingVisual={DownloadIcon} onClick={() => download(text, `generated-code.${extension}`)}>Download</Button></ButtonGroup></div><pre><code className={className} {...props}>{children}</code></pre></div>
}

export default function MessageContent({ message }) {
  if (message.role === 'tool') {
    const label = message.metadata?.tool_name || 'Tool result'
    return <Details className="tool-result" open><summary>{message.metadata?.server_name ? `${message.metadata.server_name} · ` : ''}{label}</summary><pre>{message.content}</pre></Details>
  }
  return <div className="message-content markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} components={{ code: CodeBlock, a: props => <a {...props} target="_blank" rel="noreferrer" /> }}>{message.content}</ReactMarkdown>{message.role === 'assistant' && message.content && <div className="response-actions"><Button size="small" variant="invisible" leadingVisual={DownloadIcon} onClick={() => download(message.content, `local-ai-response-${Date.now()}.md`, 'text/markdown')}>Download</Button></div>}</div>
}
