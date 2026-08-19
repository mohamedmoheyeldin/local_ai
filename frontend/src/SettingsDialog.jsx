import { useEffect, useRef, useState } from 'react'
import { Button, Checkbox, Dialog, Flash, FormControl, IconButton, LinkButton, Select, TextInput, Textarea } from '@primer/react'
import { ArchiveIcon, DatabaseIcon, DownloadIcon, GearIcon, KeyIcon, PackageIcon, PersonIcon, PulseIcon, RepoIcon, ServerIcon, ShieldLockIcon, SyncIcon } from '@primer/octicons-react'
import McpServers from './McpServers.jsx'
import { ActivitySettings, DataSettings, PerformanceSettings, WorkspaceSettings } from './AdvancedSettings.jsx'
import { DataCard, DeleteButton, EmptyState, Field, FormActions, SectionHeading, SubsectionHeading } from './PrimerUI.jsx'

const emptyResource = { name: '', resource_type: 'website', url: '', username: '', password: '', notes: '' }
const tabs = [
  ['model', 'Model & runtime', 'Model, performance, startup', GearIcon],
  ['resources', 'Local resources', 'Websites, accounts, services', PersonIcon],
  ['mcp', 'MCP servers', 'Tools, data, integrations', ServerIcon],
  ['workspaces', 'Workspaces', 'Approved project folders', RepoIcon],
  ['activity', 'Activity', 'Local and MCP tool history', ShieldLockIcon],
  ['performance', 'Performance', 'GPU, speed, presets', PulseIcon],
  ['data', 'Backup', 'Encrypted recovery', ArchiveIcon],
]

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']; const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index > 2 ? 1 : 0)} ${units[index]}`
}

function ModelSettings({ models, settings, runtime, draft, update, onRefresh, onSelect, onRuntime, onSave, busy }) {
  const selected = models.find(model => model.relative_path === settings.selected_model)
  const activeModel = runtime.model
  const changed = JSON.stringify(draft) !== JSON.stringify(settings)
  return <div className="settings-section">
    <SectionHeading title="Model & runtime" description="Choose the local GGUF model and control how llama.cpp runs it." actions={<IconButton icon={SyncIcon} aria-label="Scan model directory" onClick={onRefresh} disabled={busy} />} />
    <Field label="Selected model"><Select block value={settings.selected_model || ''} onChange={event => onSelect(event.target.value)} disabled={busy || runtime.managed}><Select.Option value="">{models.length ? 'Choose a GGUF model' : 'No GGUF models found'}</Select.Option>{models.map(model => <Select.Option key={model.id} value={model.relative_path}>{model.name} · {formatBytes(model.size_bytes)}</Select.Option>)}</Select></Field>
    <div className="summary-box"><span className={`status-indicator ${runtime.state}`}></span><div className="summary-box-copy"><strong>{runtime.state === 'checking' ? 'Checking local model' : runtime.state === 'ready' ? activeModel ? `Using ${activeModel.display_name}` : 'Model ready' : runtime.state === 'starting' ? 'Model loading' : 'Model stopped'}</strong><span>{runtime.state === 'checking' ? 'Reading the local llama.cpp runtime' : runtime.state === 'ready' && activeModel ? [activeModel.context_size ? `${Number(activeModel.context_size).toLocaleString()} context` : '', runtime.managed ? 'Managed by this app' : 'Live llama.cpp server'].filter(Boolean).join(' · ') : selected ? selected.relative_path : 'Place a .gguf file in models/'}</span></div></div>
    <Button variant={runtime.managed ? 'danger' : 'primary'} onClick={() => onRuntime(runtime.managed ? 'stop' : 'start')} disabled={busy || (runtime.healthy && !runtime.managed) || (!runtime.managed && !settings.selected_model)}>{runtime.managed ? 'Stop model' : runtime.healthy ? 'External model connected' : 'Start model'}</Button>
    <div className="subsection"><SubsectionHeading title="Runtime performance" description="Changes apply the next time a managed model starts." />
      <div className="form-grid">
        <Field label="Context"><TextInput block type="number" min="512" max="262144" value={draft.context_size ?? 8192} onChange={event => update('context_size', Number(event.target.value))} /></Field>
        <Field label="GPU layers"><TextInput block type="number" min="0" max="9999" value={draft.gpu_layers ?? 0} onChange={event => update('gpu_layers', Number(event.target.value))} /></Field>
        <Field label="CPU threads"><TextInput block type="number" min="0" max="512" value={draft.threads ?? 0} onChange={event => update('threads', Number(event.target.value))} /></Field>
        <Field label="Parallel slots"><TextInput block type="number" min="1" max="32" value={draft.parallel ?? 1} onChange={event => update('parallel', Number(event.target.value))} /></Field>
        <Field label="Prompt cache RAM (MB)"><TextInput block type="number" min="0" value={draft.cache_ram_mb ?? 256} onChange={event => update('cache_ram_mb', Number(event.target.value))} /></Field>
      </div>
      <div className="permission-grid" style={{ marginTop: 16 }}>
        <FormControl><Checkbox id="flash-attention" checked={draft.flash_attention ?? true} onChange={event => update('flash_attention', event.target.checked)} /><FormControl.Label htmlFor="flash-attention">Flash attention</FormControl.Label></FormControl>
        <FormControl><Checkbox id="auto-start-model" checked={draft.auto_start ?? false} onChange={event => update('auto_start', event.target.checked)} /><FormControl.Label htmlFor="auto-start-model">Start selected model with app</FormControl.Label></FormControl>
        <FormControl><Checkbox id="auto-tune-host" checked={draft.auto_tune ?? true} onChange={event => update('auto_tune', event.target.checked)} /><FormControl.Label htmlFor="auto-tune-host">Retune when this computer's hardware changes</FormControl.Label><FormControl.Caption>Manual performance changes turn automatic tuning off until recommendations are applied again.</FormControl.Caption></FormControl>
      </div>
      <FormActions><Button variant="primary" disabled={!changed || busy || runtime.managed} onClick={() => onSave(draft)}>Save runtime settings</Button></FormActions>
    </div>
    <Flash sx={{ mt: 3 }}>{models.length} model{models.length === 1 ? '' : 's'} found · {runtime.endpoint}</Flash>
  </div>
}

function ResourceSettings({ resources, onAdd, onEdit, onDuplicate, onDelete, busy }) {
  const [resourceDraft, setResourceDraft] = useState(emptyResource)
  const [editingResource, setEditingResource] = useState(null)
  const update = (key, value) => setResourceDraft(current => ({ ...current, [key]: value }))
  async function submit(event) {
    event.preventDefault(); if (!resourceDraft.name.trim()) return
    const saved = editingResource ? await onEdit(editingResource, resourceDraft) : await onAdd(resourceDraft)
    if (saved) { setResourceDraft(emptyResource); setEditingResource(null) }
  }
  return <div className="settings-section">
    <SectionHeading title="Local resources" description="Add websites and services the local AI should know are available to you." />
    <Flash className="privacy-banner"><KeyIcon size={16} /> <strong>Stored only on this computer.</strong> Passwords stay masked and are never included in AI prompts.</Flash>
    <form onSubmit={submit}>
      <div className="form-grid">
        <Field label="Name" required><TextInput block maxLength={120} value={resourceDraft.name} onChange={event => update('name', event.target.value)} placeholder="Expedia" /></Field>
        <Field label="Type"><Select block value={resourceDraft.resource_type} onChange={event => update('resource_type', event.target.value)}><Select.Option value="website">Website</Select.Option><Select.Option value="email">Email</Select.Option><Select.Option value="cloud-drive">Cloud drive</Select.Option><Select.Option value="developer">Developer service</Select.Option><Select.Option value="other">Other</Select.Option></Select></Field>
        <Field label="Website or service URL" className="wide"><TextInput block type="url" maxLength={2000} value={resourceDraft.url} onChange={event => update('url', event.target.value)} placeholder="https://www.expedia.com/" /></Field>
        <Field label="Username or email"><TextInput block autoComplete="username" maxLength={320} value={resourceDraft.username} onChange={event => update('username', event.target.value)} /></Field>
        <Field label="Password"><TextInput block type="password" autoComplete="new-password" maxLength={2000} value={resourceDraft.password} onChange={event => update('password', event.target.value)} placeholder="Optional" /></Field>
        <Field label="Notes for Local AI" className="wide"><Textarea block maxLength={4000} rows={4} value={resourceDraft.notes} onChange={event => update('notes', event.target.value)} placeholder="Purpose, preferences, or useful limitations" /></Field>
      </div>
      <FormActions>{editingResource && <Button onClick={() => { setEditingResource(null); setResourceDraft(emptyResource) }}>Cancel</Button>}<Button variant="primary" disabled={busy || !resourceDraft.name.trim()} type="submit">{editingResource ? 'Save changes' : 'Add local resource'}</Button></FormActions>
    </form>
    <div className="data-list">{resources.length === 0 && <EmptyState title="No local resources yet" description="Add a website, email account, cloud drive, or developer service." />}{resources.map(resource => <DataCard key={resource.id} title={resource.name} label={resource.resource_type.replace('-', ' ')} meta={resource.url} detail={[resource.username, resource.has_password ? 'Password saved' : '', resource.notes].filter(Boolean).join(' · ')} actions={<><Button size="small" onClick={() => { setEditingResource(resource.id); setResourceDraft({ name: resource.name, resource_type: resource.resource_type, url: resource.url, username: resource.username, password: '', notes: resource.notes }) }}>Edit</Button><Button size="small" onClick={() => onDuplicate(resource.id)}>Duplicate</Button><DeleteButton onClick={() => onDelete(resource.id)} disabled={busy} /></>} />)}</div>
  </div>
}

export default function SettingsDialog({ open, onClose, models, settings, runtime, resources, mcpServers, providers, workspaces, audit, metrics, hostProfile, onRefresh, onSelect, onRuntime, onSave, onAddResource, onEditResource, onDuplicateResource, onDeleteResource, onAddMcpServer, onEditMcpServer, onDuplicateMcpServer, onDeleteMcpServer, onRevokeMcpServer, onToggleMcpServer, onTestMcpServer, onOAuthMcpServer, onAddWorkspace, onSelectWorkspace, onDeleteWorkspace, onRefreshAudit, onClearAudit, onBackup, onRestore, onRefreshMetrics, onRefreshHostProfile, onApplyHostRecommendations, onPreset, busy }) {
  const [tab, setTab] = useState('model')
  const [draft, setDraft] = useState(settings)
  const initialFocusRef = useRef(null)
  const panelRef = useRef(null)
  useEffect(() => { setDraft(settings) }, [settings])
  if (!open) return null
  const update = (key, value) => setDraft(current => ({ ...current, [key]: value }))
  const selectTab = id => { setTab(id); requestAnimationFrame(() => panelRef.current?.scrollTo({ top: 0 })) }
  const onTabKeyDown = (event, index) => {
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1) + tabs.length) % tabs.length
    selectTab(tabs[nextIndex][0])
    requestAnimationFrame(() => document.getElementById(`settings-tab-${tabs[nextIndex][0]}`)?.focus())
  }
  return <Dialog className="settings-dialog" title="Settings" subtitle="Local AI" onClose={onClose} initialFocusRef={initialFocusRef} position={{ narrow: 'fullscreen', regular: 'fullscreen' }} width="100vw" height="100vh">
    <div className="settings-shell">
      <nav className="settings-navigation" aria-label="Settings sections" role="tablist">{tabs.map(([id, label, description, Icon], index) => <button type="button" id={`settings-tab-${id}`} className={`settings-tab${tab === id ? ' active' : ''}`} key={id} ref={id === 'model' ? initialFocusRef : undefined} role="tab" tabIndex={tab === id ? 0 : -1} aria-selected={tab === id} aria-controls={`settings-panel-${id}`} onKeyDown={event => onTabKeyDown(event, index)} onClick={() => selectTab(id)}><Icon size={16} /><span><strong>{label}</strong><small>{description}</small></span></button>)}</nav>
      <main className="settings-panel" ref={panelRef}>
        <div className="settings-panel-inner" id={`settings-panel-${tab}`} role="tabpanel" aria-labelledby={`settings-tab-${tab}`}><div className="settings-panel-actions"><LinkButton href="/api/export" target="_blank" leadingVisual={DownloadIcon}>Export data</LinkButton></div>
        {tab === 'model' && <ModelSettings models={models} settings={settings} runtime={runtime} draft={draft} update={update} onRefresh={onRefresh} onSelect={onSelect} onRuntime={onRuntime} onSave={onSave} busy={busy} />}
        {tab === 'resources' && <ResourceSettings resources={resources} onAdd={onAddResource} onEdit={onEditResource} onDuplicate={onDuplicateResource} onDelete={onDeleteResource} busy={busy} />}
        {tab === 'mcp' && <McpServers servers={mcpServers} providers={providers} onAdd={onAddMcpServer} onEdit={onEditMcpServer} onDuplicate={onDuplicateMcpServer} onDelete={onDeleteMcpServer} onRevoke={onRevokeMcpServer} onToggle={onToggleMcpServer} onTest={onTestMcpServer} onOAuth={onOAuthMcpServer} busy={busy} />}
        {tab === 'workspaces' && <WorkspaceSettings workspaces={workspaces} workspaceRoot={hostProfile?.paths?.home} onAdd={onAddWorkspace} onSelect={onSelectWorkspace} onDelete={onDeleteWorkspace} busy={busy} />}
        {tab === 'activity' && <ActivitySettings events={audit} onRefresh={onRefreshAudit} onClear={onClearAudit} />}
        {tab === 'performance' && <PerformanceSettings metrics={metrics} runtime={runtime} settings={settings} hostProfile={hostProfile} onRefresh={() => { onRefreshMetrics(); onRefreshHostProfile() }} onApplyRecommended={onApplyHostRecommendations} onPreset={onPreset} onSaveCustom={onSave} busy={busy} />}
        {tab === 'data' && <DataSettings onBackup={onBackup} onRestore={onRestore} busy={busy} />}</div>
      </main>
    </div>
  </Dialog>
}
