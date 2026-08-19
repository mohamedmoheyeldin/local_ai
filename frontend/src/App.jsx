import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { ActionList, ActionMenu, Button, Flash, IconButton, PageLayout, Spinner, Textarea, useConfirm } from '@primer/react'
import { AgentIcon, CloudIcon, CommentDiscussionIcon, DeviceDesktopIcon, GearIcon, GlobeIcon, HubotIcon, LockIcon, MoonIcon, PaperAirplaneIcon, PersonIcon, SidebarCollapseIcon, SidebarExpandIcon, SquareIcon, SunIcon, ToolsIcon } from '@primer/octicons-react'
import { api } from './api.js'
import AttachmentMenu from './AttachmentMenu.jsx'
import ConversationList from './ConversationList.jsx'

const MessageContent = lazy(() => import('./MessageContent.jsx'))
const ConversationDrawer = lazy(() => import('./ConversationDrawer.jsx'))
const HandoffDialog = lazy(() => import('./HandoffDialog.jsx'))
const SettingsDialog = lazy(() => import('./SettingsDialog.jsx'))

function ThemeMenu({ colorMode, setColorMode }) {
  const choices = [['day', 'Light', SunIcon], ['night', 'Dark', MoonIcon], ['auto', 'System', DeviceDesktopIcon]]
  const ActiveIcon = choices.find(([id]) => id === colorMode)?.[2] || DeviceDesktopIcon
  return <ActionMenu><ActionMenu.Button aria-label="Theme" leadingVisual={ActiveIcon}><span className="header-button-label">Theme</span></ActionMenu.Button><ActionMenu.Overlay align="end"><ActionList selectionVariant="single">{choices.map(([id, label, Icon]) => <ActionList.Item key={id} selected={colorMode === id} onSelect={() => setColorMode(id)}><ActionList.LeadingVisual><Icon /></ActionList.LeadingVisual>{label}</ActionList.Item>)}</ActionList></ActionMenu.Overlay></ActionMenu>
}

function AppHeader({ runtime, messages, title, sidebarCollapsed, colorMode, setColorMode, onShowSidebar, onMobileChats, onHandoff, onSettings }) {
  return <div className="app-header">
    <div className="chat-title-group">
      <IconButton className="desktop-sidebar-open" icon={SidebarExpandIcon} aria-label="Show chat sidebar" aria-controls="chat-sidebar" aria-expanded={!sidebarCollapsed} onClick={onShowSidebar} />
      <IconButton className="mobile-chats-open" icon={CommentDiscussionIcon} aria-label="Open chats" onClick={onMobileChats} />
      <div className="chat-title"><strong>{title}</strong><span>Local AI</span></div>
    </div>
    <div className="header-actions">
      <div className="runtime-pill"><span className={`status-indicator ${runtime.state}`}></span><span>{runtime.state === 'checking' ? 'Checking local model…' : runtime.healthy ? runtime.model?.display_name || 'Local model ready' : 'Model unavailable'}</span></div>
      <Button aria-label="Cloud handoff" leadingVisual={CloudIcon} onClick={onHandoff} disabled={!messages.length}><span className="header-button-label">Cloud handoff</span></Button>
      <ThemeMenu colorMode={colorMode} setColorMode={setColorMode} />
      <IconButton icon={GearIcon} aria-label="Settings" onClick={onSettings} />
    </div>
  </div>
}

function AppSidebar({ conversations, currentId, onSelect, onNew, onArchive, onDelete, onSearch, onCollapse }) {
  return <aside className="sidebar-shell" aria-label="Chat history">
    <div className="sidebar-header">
      <div className="app-brand"><span className="app-brand-mark"><AgentIcon size={20} /></span><div className="app-brand-copy"><strong>Local AI</strong><span>Your private AI workspace</span></div></div>
      <IconButton icon={SidebarCollapseIcon} variant="invisible" aria-label="Hide chat sidebar" aria-controls="chat-sidebar" aria-expanded="true" onClick={onCollapse} />
    </div>
    <ConversationList compact conversations={conversations} currentId={currentId} onSelect={onSelect} onNew={onNew} onArchive={onArchive} onDelete={onDelete} onSearch={onSearch} />
    <div className="sidebar-privacy"><LockIcon size={12} /><span>Chats stay on this computer</span></div>
  </aside>
}

export default function App({ colorMode, setColorMode }) {
  const [models, setModels] = useState([])
  const [settings, setSettings] = useState({})
  const [runtime, setRuntime] = useState({ state: 'checking', managed: false, healthy: false, endpoint: '' })
  const [resources, setResources] = useState([])
  const [mcpServers, setMcpServers] = useState([])
  const [providers, setProviders] = useState([])
  const [workspaces, setWorkspaces] = useState([])
  const [audit, setAudit] = useState([])
  const [metrics, setMetrics] = useState({ presets: {} })
  const [hostProfile, setHostProfile] = useState(null)
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [contextSources, setContextSources] = useState([])
  const [indexing, setIndexing] = useState(false)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [researching, setResearching] = useState(false)
  const [notice, setNotice] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [conversationsOpen, setConversationsOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('local-ai-sidebar-collapsed') === 'true')
  const [handoffOpen, setHandoffOpen] = useState(false)
  const [pendingTool, setPendingTool] = useState(null)
  const scrollRef = useRef(null)
  const followLatestRef = useRef(true)
  const abortRef = useRef(null)
  const confirm = useConfirm()

  useEffect(() => { localStorage.setItem('local-ai-sidebar-collapsed', String(sidebarCollapsed)) }, [sidebarCollapsed])

  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      api('/api/runtime').then(setRuntime),
      api('/api/models').then(data => setModels(data.models)),
      api('/api/settings').then(setSettings),
      api('/api/resources').then(data => setResources(data.resources)),
      api('/api/mcp-servers').then(data => setMcpServers(data.servers)),
      api('/api/conversations').then(data => setConversations(data.conversations)),
      api('/api/mcp/providers').then(data => setProviders(data.providers)),
      api('/api/workspaces').then(data => setWorkspaces(data.workspaces)),
      api('/api/mcp-audit').then(data => setAudit(data.events)),
      api('/api/runtime/metrics').then(setMetrics),
      api('/api/system/profile').then(setHostProfile),
    ])
    const failure = results.find(result => result.status === 'rejected')
    setNotice(failure ? failure.reason?.message || 'Some local data could not be loaded' : '')
  }, [])

  useEffect(() => {
    Promise.allSettled([
      api('/api/runtime').then(setRuntime),
      api('/api/conversations').then(data => setConversations(data.conversations)),
      api('/api/workspaces').then(data => setWorkspaces(data.workspaces)),
    ]).then(results => {
      const failure = results.find(result => result.status === 'rejected')
      if (failure) setNotice(failure.reason?.message || 'Some local data could not be loaded')
    })
  }, [])
  useEffect(() => { if (settingsOpen) load() }, [settingsOpen, load])
  useEffect(() => { const timer = setInterval(async () => { try { setRuntime(await api('/api/runtime')) } catch {} }, 2500); return () => clearInterval(timer) }, [])
  useEffect(() => {
    if (!followLatestRef.current) return
    const frame = requestAnimationFrame(() => {
      const viewport = scrollRef.current
      if (viewport) viewport.scrollTop = viewport.scrollHeight
    })
    return () => cancelAnimationFrame(frame)
  }, [messages, generating])

  const searchConversations = useCallback(async query => { try { setConversations((await api(`/api/conversations?query=${encodeURIComponent(query)}`)).conversations) } catch (error) { setNotice(error.message) } }, [])
  async function selectConversation(id) { try { const data = await api(`/api/conversations/${id}`); setConversationId(id); setMessages(data.messages.map(message => ({ role: message.role, content: message.content, metadata: message.metadata }))); setContextSources(data.context || []); setNotice('') } catch (error) { setNotice(error.message) } }
  function newConversation() { setConversationId(null); setMessages([]); setContextSources([]); setInput(''); setNotice('') }
  async function archiveConversation(id) { try { await api(`/api/conversations/${id}`, { method: 'PATCH', body: JSON.stringify({ archived: true }) }); if (id === conversationId) newConversation(); await searchConversations('') } catch (error) { setNotice(error.message) } }
  async function removeConversation(id) { if (!await confirm({ title: 'Delete conversation?', content: 'This permanently removes the local conversation.', confirmButtonContent: 'Delete', confirmButtonType: 'danger' })) return; try { await api(`/api/conversations/${id}`, { method: 'DELETE' }); if (id === conversationId) newConversation(); await searchConversations('') } catch (error) { setNotice(error.message) } }

  async function refreshModels() { setBusy(true); try { const data = await api('/api/models/scan', { method: 'POST' }); setModels(data.models); setNotice(`${data.count} model${data.count === 1 ? '' : 's'} found`) } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function selectModel(relativePath) { if (!relativePath) return; setBusy(true); try { await api('/api/models/select', { method: 'POST', body: JSON.stringify({ relative_path: relativePath }) }); await load() } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function changeRuntime(action) { setBusy(true); setNotice(action === 'start' ? 'Starting local model…' : 'Stopping local model…'); try { setRuntime(await api(`/api/runtime/${action}`, { method: 'POST' })); setTimeout(load, 1200) } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function saveSettings(draft) { const allowed = ['model_host','model_port','context_size','gpu_layers','threads','parallel','cache_ram_mb','flash_attention','auto_start','auto_tune','llama_executable']; const body = Object.fromEntries(allowed.filter(key => key in draft && draft[key] !== settings[key]).map(key => [key, draft[key]])); setBusy(true); try { setSettings(await api('/api/settings', { method: 'PATCH', body: JSON.stringify(body) })); setHostProfile(await api('/api/system/profile')); setNotice('Settings saved') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function addResource(resource) { setBusy(true); try { await api('/api/resources', { method: 'POST', body: JSON.stringify(resource) }); setResources((await api('/api/resources')).resources); setNotice('Local resource saved'); return true } catch (error) { setNotice(error.message); return false } finally { setBusy(false) } }
  async function removeResource(id) { setBusy(true); try { await api(`/api/resources/${id}`, { method: 'DELETE' }); setResources(current => current.filter(resource => resource.id !== id)); setNotice('Local resource removed') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function editResource(id, resource) { const payload = { ...resource }; if (!payload.password) delete payload.password; setBusy(true); try { await api(`/api/resources/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }); setResources((await api('/api/resources')).resources); setNotice('Resource updated'); return true } catch (error) { setNotice(error.message); return false } finally { setBusy(false) } }
  async function duplicateResource(id) { setBusy(true); try { await api(`/api/resources/${id}/duplicate`, { method: 'POST' }); setResources((await api('/api/resources')).resources); setNotice('Resource copied') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }

  async function addMcpServer(server) { setBusy(true); try { await api('/api/mcp-servers', { method: 'POST', body: JSON.stringify(server) }); setMcpServers((await api('/api/mcp-servers')).servers); setNotice('MCP server saved'); return true } catch (error) { setNotice(error.message); return false } finally { setBusy(false) } }
  async function removeMcpServer(id) { if (!await confirm({ title: 'Remove MCP server?', content: 'The local server configuration and saved credentials will be removed.', confirmButtonContent: 'Remove server', confirmButtonType: 'danger' })) return; setBusy(true); try { await api(`/api/mcp-servers/${id}`, { method: 'DELETE' }); setMcpServers(current => current.filter(server => server.id !== id)); setNotice('MCP server removed') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function editMcpServer(id, server) { setBusy(true); try { await api(`/api/mcp-servers/${id}`, { method: 'PATCH', body: JSON.stringify(server) }); setMcpServers((await api('/api/mcp-servers')).servers); setNotice('MCP server updated'); return true } catch (error) { setNotice(error.message); return false } finally { setBusy(false) } }
  async function duplicateMcpServer(id) { setBusy(true); try { await api(`/api/mcp-servers/${id}/duplicate`, { method: 'POST' }); setMcpServers((await api('/api/mcp-servers')).servers); setNotice('MCP server copied') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function revokeMcpServer(id) { if (!await confirm({ title: 'Remove saved access?', content: 'Credentials will be deleted locally and the server disabled. Provider-side access may also need to be revoked.', confirmButtonContent: 'Remove access', confirmButtonType: 'danger' })) return; setBusy(true); try { await api(`/api/mcp-servers/${id}/credentials`, { method: 'DELETE' }); setMcpServers((await api('/api/mcp-servers')).servers); setNotice('Credentials revoked') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function toggleMcpServer(id, enabled) { setBusy(true); try { const updated = await api(`/api/mcp-servers/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }); setMcpServers(current => current.map(server => server.id === id ? updated : server)); setNotice(`MCP server ${enabled ? 'enabled' : 'disabled'}`) } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function testMcpServer(id) { setBusy(true); setNotice('Testing MCP connection…'); try { const result = await api(`/api/mcp-servers/${id}/test`, { method: 'POST' }); await load(); setNotice(`Connected · ${result.capabilities.tools.length} tools available`) } catch (error) { await load(); setNotice(error.message) } finally { setBusy(false) } }
  async function oauthMcpServer(id) { setBusy(true); try { const result = await api(`/api/mcp-servers/${id}/oauth/start`, { method: 'POST' }); window.open(result.authorization_url, '_blank', 'noopener,noreferrer'); setNotice('Finish authorization in the new window, then test the connection.') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }

  async function addWorkspace(draft) { setBusy(true); try { await api('/api/workspaces', { method: 'POST', body: JSON.stringify(draft) }); setWorkspaces((await api('/api/workspaces')).workspaces); setNotice('Workspace approved'); return true } catch (error) { setNotice(error.message); return false } finally { setBusy(false) } }
  async function chooseWorkspace(id) { try { await api(`/api/workspaces/${id}/select`, { method: 'PATCH' }); setWorkspaces((await api('/api/workspaces')).workspaces); setNotice('Workspace selected') } catch (error) { setNotice(error.message) } }
  async function removeWorkspace(id) { try { await api(`/api/workspaces/${id}`, { method: 'DELETE' }); setWorkspaces((await api('/api/workspaces')).workspaces); setNotice('Workspace removed') } catch (error) { setNotice(error.message) } }
  async function refreshAudit() { try { setAudit((await api('/api/mcp-audit')).events) } catch (error) { setNotice(error.message) } }
  async function clearAudit() { if (!await confirm({ title: 'Clear MCP activity?', content: 'This permanently deletes the local MCP activity history.', confirmButtonContent: 'Clear activity', confirmButtonType: 'danger' })) return; await api('/api/mcp-audit', { method: 'DELETE' }); setAudit([]) }
  async function refreshMetrics() { try { setMetrics(await api('/api/runtime/metrics')) } catch (error) { setNotice(error.message) } }
  async function refreshHostProfile() { try { setHostProfile(await api('/api/system/profile')) } catch (error) { setNotice(error.message) } }
  async function applyHostRecommendations() { setBusy(true); try { const result = await api('/api/system/apply-recommended', { method: 'POST' }); setSettings(result.settings); setHostProfile(await api('/api/system/profile')); setNotice('Best settings for this computer applied') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function applyPreset(name) { setBusy(true); try { const result = await api(`/api/runtime/presets/${name}`, { method: 'POST' }); setSettings(result.settings); setNotice(`${name.replace('-', ' ')} preset applied`) } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function downloadBackup(passphrase) { setBusy(true); try { const response = await fetch('/api/backup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ passphrase }) }); if (!response.ok) throw new Error((await response.json()).detail); const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `local-ai-${new Date().toISOString().slice(0,10)}.laibak`; anchor.click(); URL.revokeObjectURL(url); setNotice('Encrypted backup downloaded') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }
  async function restoreBackup(file, passphrase) { if (!await confirm({ title: 'Restore this backup?', content: 'Current local data will be replaced. This operation cannot be undone.', confirmButtonContent: 'Restore and replace', confirmButtonType: 'danger' })) return; setBusy(true); try { const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ''; for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000)); await api('/api/restore', { method: 'POST', body: JSON.stringify({ passphrase, backup_base64: btoa(binary), confirmation: 'RESTORE' }) }); await load(); setNotice('Backup restored. Restart the app before continuing.') } catch (error) { setNotice(error.message) } finally { setBusy(false) } }

  async function ensureConversation() {
    if (conversationId) return conversationId
    const created = await api('/api/conversations', { method: 'POST', body: JSON.stringify({}) })
    setConversationId(created.id)
    await searchConversations('')
    return created.id
  }
  async function attachContext(files, relativePaths) {
    setIndexing(true); setNotice(`Indexing ${files.length} selected file${files.length === 1 ? '' : 's'} locally…`)
    try {
      const activeConversation = await ensureConversation()
      const body = new FormData()
      files.forEach(file => body.append('files', file, file.name))
      body.append('relative_paths', JSON.stringify(relativePaths))
      const data = await new Promise((resolve, reject) => {
        const request = new XMLHttpRequest()
        request.open('POST', `/api/conversations/${activeConversation}/context`)
        request.responseType = 'json'
        request.upload.onprogress = event => { if (event.lengthComputable) setNotice(`Uploading locally · ${Math.round(event.loaded / event.total * 100)}%`) }
        request.upload.onload = () => setNotice('Upload complete · indexing locally…')
        request.onerror = () => reject(new Error('Local upload failed'))
        request.onload = () => request.status >= 200 && request.status < 300 ? resolve(request.response || {}) : reject(new Error(request.response?.detail || `Upload failed (${request.status})`))
        request.send(body)
      })
      setContextSources((await api(`/api/conversations/${activeConversation}/context`)).sources)
      const skipped = data.skipped?.length || 0
      setNotice(`${data.count} file${data.count === 1 ? '' : 's'} indexed${skipped ? ` · ${skipped} skipped` : ''}`)
    } catch (error) { setNotice(error.message) } finally { setIndexing(false) }
  }
  async function removeContext(source) {
    if (!conversationId) return
    try {
      await api(`/api/conversations/${conversationId}/context/${source.id}`, { method: 'DELETE' })
      setContextSources(current => current.filter(item => item.id !== source.id))
      setNotice(`${source.relative_path} removed from this conversation`)
    } catch (error) { setNotice(error.message) }
  }

  async function runMessage(text, baseMessages = messages) {
    if (!text || generating) return
    let activeConversation = conversationId
    let pendingTokens = '', flushTimer = null
    const flushTokens = () => {
      if (!pendingTokens) return
      const content = pendingTokens; pendingTokens = ''
      setMessages(current => { const copy = [...current]; const last = copy.length - 1; copy[last] = { ...copy[last], content: copy[last].content + content }; return copy })
    }
    const queueToken = content => {
      pendingTokens += content
      if (!flushTimer) flushTimer = window.setTimeout(() => { flushTimer = null; flushTokens() }, 40)
    }
    try {
      if (!activeConversation) activeConversation = await ensureConversation()
      const next = [...baseMessages, { role: 'user', content: text }]
      setMessages([...next, { role: 'assistant', content: '' }]); setInput(''); setGenerating(true); setResearching(true); setNotice('')
      const controller = new AbortController(); abortRef.current = controller
      const response = await fetch('/api/chat/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: next, conversation_id: activeConversation }), signal: controller.signal })
      setResearching(false)
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || `Request failed (${response.status})`) }
      const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { value, done } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || ''
        for (const line of lines) { if (!line.trim()) continue; const eventData = JSON.parse(line); if (eventData.type === 'token') queueToken(eventData.content); if (eventData.type === 'error') throw new Error(eventData.error); if (eventData.type === 'approval') { setPendingTool(eventData); setNotice(`${eventData.server_name} wants to run ${eventData.tool_name}`) } }
      }
      if (flushTimer) { clearTimeout(flushTimer); flushTimer = null }; flushTokens()
      await searchConversations('')
    } catch (error) { setNotice(error.name === 'AbortError' ? 'Generation stopped' : error.message) } finally { if (flushTimer) clearTimeout(flushTimer); flushTokens(); setGenerating(false); setResearching(false); abortRef.current = null }
  }
  async function send(event) { event?.preventDefault(); const text = input.trim(); if (text) await runMessage(text) }
  async function approveTool() { const pending = pendingTool; if (!pending) return; setBusy(true); try { const endpoint = pending.local ? '/api/local-tools/call' : `/api/mcp-servers/${pending.server_id}/call`; const data = await api(endpoint, { method: 'POST', body: JSON.stringify({ tool_name: pending.tool_name, arguments: pending.arguments, approved: true, conversation_id: conversationId }) }); const toolMessage = { role: 'tool', content: JSON.stringify(data.result, null, 2), metadata: { server_name: pending.server_name, tool_name: pending.tool_name } }; const history = [...messages.filter(message => message.content), toolMessage]; setMessages(history); setPendingTool(null); await refreshAudit(); setBusy(false); await runMessage('Continue the original task using the approved tool result.', history) } catch (error) { setNotice(error.message); setBusy(false) } }

  const currentTitle = conversations.find(item => item.id === conversationId)?.title || 'New chat'

  return <>
    <PageLayout className="app-shell" containerWidth="full" padding="none" rowGap="none" columnGap="none">
      <PageLayout.Sidebar id="chat-sidebar" className="chat-sidebar" aria-label="Chat history" width={{ min: '248px', default: '280px', max: '320px' }} padding="none" divider="line" hidden={sidebarCollapsed ? true : { narrow: true }}>
        <AppSidebar conversations={conversations} currentId={conversationId} onSelect={selectConversation} onNew={newConversation} onArchive={archiveConversation} onDelete={removeConversation} onSearch={searchConversations} onCollapse={() => setSidebarCollapsed(true)} />
      </PageLayout.Sidebar>
      <PageLayout.Header className="main-header-shell" padding="none" divider="line">
        <AppHeader runtime={runtime} messages={messages} title={currentTitle} sidebarCollapsed={sidebarCollapsed} colorMode={colorMode} setColorMode={setColorMode} onShowSidebar={() => setSidebarCollapsed(false)} onMobileChats={() => setConversationsOpen(true)} onHandoff={() => setHandoffOpen(true)} onSettings={() => setSettingsOpen(true)} />
      </PageLayout.Header>
      <PageLayout.Content className="chat-main" width="full" padding="none">
      <div className="message-scroll" ref={scrollRef} onScroll={event => {
        const viewport = event.currentTarget
        followLatestRef.current = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 120
      }}><div className="message-list" aria-live="polite">
        {messages.map((message, index) => <article key={`${message.role}-${index}`} className={`message-row ${message.role}`}>
          {message.role !== 'user' && <div className="message-avatar">{message.role === 'tool' ? <ToolsIcon size={16} /> : <HubotIcon size={17} />}</div>}
          <div className="message-body">{message.role !== 'user' && <div className="message-author"><strong>{message.role === 'tool' ? 'Tool' : 'Local AI'}</strong><span>{message.role === 'assistant' ? 'local model' : 'approved result'}</span></div>}<Suspense fallback={<Spinner size="small" />}><MessageContent message={message} /></Suspense></div>
        </article>)}
        {generating && !messages.at(-1)?.content && <div className="thinking-row">{researching ? <GlobeIcon size={16} /> : <Spinner size="small" />} {researching ? 'Searching the web for current information…' : 'Local AI is thinking…'}</div>}
      </div></div>
      <div className="composer-dock"><div className="composer-wrap">
        {pendingTool && <div className="tool-approval"><div><strong>Allow {pendingTool.server_name} to run {pendingTool.tool_name}?</strong><span>{pendingTool.local ? 'This can change files or run a command on this computer.' : 'Review the requested action before continuing.'}</span><code>{JSON.stringify(pendingTool.arguments, null, 2)}</code></div><div className="tool-approval-actions"><Button size="small" onClick={() => setPendingTool(null)}>Deny</Button><Button size="small" variant="primary" onClick={approveTool}>Allow once</Button></div></div>}
        {notice && <Flash className="composer-alert" role="status">{notice}</Flash>}
        <form className="composer" onSubmit={send}>
          <AttachmentMenu sources={contextSources} indexing={indexing} disabled={busy || generating} onPick={attachContext} onRemove={removeContext} />
          <Textarea aria-label="Message Local AI" value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send() } }} placeholder={runtime.state === 'checking' ? 'Checking local model…' : runtime.healthy ? 'Message Local AI' : 'Connect a local model in Settings'} disabled={!runtime.healthy || busy || generating || indexing} rows={1} />
          {generating ? <IconButton type="button" icon={SquareIcon} variant="danger" onClick={() => abortRef.current?.abort()} aria-label="Stop generating" /> : <IconButton type="submit" icon={PaperAirplaneIcon} variant="primary" disabled={!runtime.healthy || busy || indexing || !input.trim()} aria-label="Send message" />}
        </form>
        <div className="composer-note"><LockIcon size={12} /> Chats stay local. Web research shares only the current question with public search providers.</div>
      </div></div>
      </PageLayout.Content>
    </PageLayout>
    <Suspense fallback={null}>
      {conversationsOpen && <ConversationDrawer open onClose={() => setConversationsOpen(false)} conversations={conversations} currentId={conversationId} onSelect={selectConversation} onNew={newConversation} onArchive={archiveConversation} onDelete={removeConversation} onSearch={searchConversations} />}
      {handoffOpen && <HandoffDialog open onClose={() => setHandoffOpen(false)} messages={messages.filter(message => message.content)} runtime={runtime} workspaces={workspaces} conversationId={conversationId} />}
      {settingsOpen && <SettingsDialog open onClose={() => setSettingsOpen(false)} models={models} settings={settings} runtime={runtime} resources={resources} mcpServers={mcpServers} providers={providers} workspaces={workspaces} audit={audit} metrics={metrics} hostProfile={hostProfile} onRefresh={refreshModels} onSelect={selectModel} onRuntime={changeRuntime} onSave={saveSettings} onAddResource={addResource} onEditResource={editResource} onDuplicateResource={duplicateResource} onDeleteResource={removeResource} onAddMcpServer={addMcpServer} onEditMcpServer={editMcpServer} onDuplicateMcpServer={duplicateMcpServer} onDeleteMcpServer={removeMcpServer} onRevokeMcpServer={revokeMcpServer} onToggleMcpServer={toggleMcpServer} onTestMcpServer={testMcpServer} onOAuthMcpServer={oauthMcpServer} onAddWorkspace={addWorkspace} onSelectWorkspace={chooseWorkspace} onDeleteWorkspace={removeWorkspace} onRefreshAudit={refreshAudit} onClearAudit={clearAudit} onBackup={downloadBackup} onRestore={restoreBackup} onRefreshMetrics={refreshMetrics} onRefreshHostProfile={refreshHostProfile} onApplyHostRecommendations={applyHostRecommendations} onPreset={applyPreset} busy={busy || generating} />}
    </Suspense>
  </>
}
