import { useState } from 'react'
import { Button, Flash, FormControl, IconButton, TextInput } from '@primer/react'
import { DownloadIcon, FileIcon, ShieldLockIcon, SyncIcon, TrashIcon } from '@primer/octicons-react'
import { DataCard, DeleteButton, EmptyState, Field, FormActions, MetricCard, SectionHeading } from './PrimerUI.jsx'

export function WorkspaceSettings({ workspaces, workspaceRoot, onAdd, onSelect, onDelete, busy }) {
  const [draft, setDraft] = useState({ name: '', path: '' })
  return <div className="settings-section">
    <SectionHeading title="Approved workspaces" description={`Local AI and Cloud handoff can inspect only folders you approve under ${workspaceRoot || 'your user folder'}.`} />
    <form onSubmit={async event => { event.preventDefault(); if (await onAdd(draft)) setDraft({ name: '', path: '' }) }}>
      <div className="form-grid"><Field label="Name" required><TextInput block value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} placeholder="Portfolio" /></Field><Field label="Folder" required><TextInput block value={draft.path} onChange={event => setDraft({ ...draft, path: event.target.value })} placeholder={workspaceRoot ? `${workspaceRoot}${workspaceRoot.includes('\\') ? '\\' : '/'}project` : 'Choose a folder inside your user directory'} /></Field></div>
      <FormActions><Button variant="primary" type="submit" disabled={busy}>Approve workspace</Button></FormActions>
    </form>
    <div className="data-list">{workspaces.length === 0 && <EmptyState title="No approved workspaces" description="Approve a project folder to use repository context and Cloud handoff." />}{workspaces.map(item => <DataCard key={item.id} title={item.name} label={item.selected ? 'Selected' : null} meta={item.path} actions={<>{!item.selected && <Button size="small" onClick={() => onSelect(item.id)}>Select</Button>}<DeleteButton onClick={() => onDelete(item.id)} /></>} />)}</div>
  </div>
}

export function ActivitySettings({ events, onRefresh, onClear }) {
  return <div className="settings-section">
    <SectionHeading title="MCP activity" description="Review approvals, completed tools, denials, failures, and access used." actions={<><Button size="small" leadingVisual={SyncIcon} onClick={onRefresh}>Refresh</Button><Button size="small" variant="danger" leadingVisual={TrashIcon} onClick={onClear}>Clear</Button></>} />
    <div className="data-list">{events.length === 0 && <EmptyState title="No tool activity" description="MCP tool activity will appear here." />}{events.map(event => <details className="audit-event" key={event.id}><summary><strong>{event.server_name} · {event.tool_name}</strong><span>{event.outcome} · {event.created_at}</span></summary><pre>{JSON.stringify(event.arguments, null, 2)}</pre>{event.detail && <Flash variant="danger">{event.detail}</Flash>}</details>)}</div>
  </div>
}

export function DataSettings({ onBackup, onRestore, busy }) {
  const [passphrase, setPassphrase] = useState('')
  const [restoreFile, setRestoreFile] = useState(null)
  return <div className="settings-section">
    <SectionHeading title="Backup & restore" description="Create one encrypted backup containing settings, conversations, workspaces, MCP configuration, and credentials." />
    <Flash variant="warning" className="privacy-banner"><ShieldLockIcon size={16} /> <strong>Keep your passphrase safe.</strong> It cannot be recovered, and restore replaces current local data.</Flash>
    <Field label="Backup passphrase" caption="Use at least 10 characters."><TextInput block type="password" value={passphrase} onChange={event => setPassphrase(event.target.value)} minLength={10} autoComplete="new-password" /></Field>
    <FormActions>
      <Button variant="primary" leadingVisual={DownloadIcon} disabled={busy || passphrase.length < 10} onClick={() => onBackup(passphrase)}>Download encrypted backup</Button>
      <Button as="label" leadingVisual={FileIcon}>Choose backup<input hidden type="file" accept=".laibak" onChange={event => setRestoreFile(event.target.files?.[0] || null)} /></Button>
      <Button variant="danger" disabled={busy || !restoreFile || passphrase.length < 10} onClick={() => onRestore(restoreFile, passphrase)}>Restore and replace</Button>
    </FormActions>
    {restoreFile && <Flash sx={{ mt: 3 }}>Selected: {restoreFile.name}</Flash>}
  </div>
}

function compactBytes(bytes) {
  if (!bytes) return 'Not reported'
  return `${(bytes / 2 ** 30).toFixed(1)} GB`
}

export function PerformanceSettings({ metrics, runtime, hostProfile, onRefresh, onApplyRecommended, onPreset, busy }) {
  const gpu = metrics.gpu
  const hostGpu = hostProfile?.gpus?.[0]
  const platform = hostProfile?.platform
  const configuration = hostProfile?.configuration
  const runtimeDependencies = hostProfile ? Object.values(hostProfile.dependencies || {}).filter(item => item.required_at_runtime) : []
  const dependencyCount = runtimeDependencies.filter(item => item.available).length
  const dependencyTotal = runtimeDependencies.length
  return <div className="settings-section">
    <SectionHeading title="Host & performance" description="Detected hardware, automatic recommendations, live speed, and safe overrides." actions={<IconButton icon={SyncIcon} aria-label="Refresh host and performance" onClick={onRefresh} />} />
    {hostProfile ? <>
      <div className="metric-grid"><MetricCard label="Operating system" value={`${platform.system}${platform.wsl ? ` · WSL${platform.wsl_distribution ? ` (${platform.wsl_distribution})` : ''}` : ''}`} /><MetricCard label="Processor" value={hostProfile.cpu.name} /><MetricCard label="CPU cores" value={`${hostProfile.cpu.physical_cores || 'Unknown'} physical · ${hostProfile.cpu.logical_cores} logical`} /><MetricCard label="System memory" value={compactBytes(hostProfile.memory.total_bytes)} /><MetricCard label="Graphics backend" value={hostGpu ? `${hostGpu.backend} · ${hostGpu.name}` : 'CPU only'} /><MetricCard label="Data storage available" value={compactBytes(hostProfile.storage.data_free_bytes)} /><MetricCard label="Runtime requirements" value={`${dependencyCount} of ${dependencyTotal} ready`} /><MetricCard label="Automatic tuning" value={configuration?.automatic ? configuration.matches_host ? 'On · current' : 'On · update available' : 'Off · custom settings'} /></div>
      <Flash variant={Object.keys(configuration?.differences || {}).length ? 'warning' : 'success'} sx={{ mt: 3 }}><strong>{Object.keys(configuration?.differences || {}).length ? 'Different settings are recommended for this host.' : 'Runtime settings match this computer.'}</strong><ul className="recommendation-list">{hostProfile.recommended.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>{configuration?.environment_overrides?.length > 0 && <div>Environment overrides: {configuration.environment_overrides.join(', ')}</div>}</Flash>
      <FormActions><Button variant="primary" onClick={onApplyRecommended} disabled={busy || runtime.managed}>Apply best settings for this computer</Button></FormActions>
    </> : <Flash>Detecting this computer's capabilities…</Flash>}
    <div className="subsection"><SectionHeading title="Live performance" description="Current model activity and recent generation measurements." />
    <div className="metric-grid"><MetricCard label="Active model" value={runtime.model?.display_name || 'Not connected'} /><MetricCard label="Average speed" value={metrics.average_tokens_per_second ? `${metrics.average_tokens_per_second} tok/s` : 'No samples yet'} /><MetricCard label="GPU" value={gpu?.name || 'Not reported'} /><MetricCard label="VRAM" value={gpu ? `${gpu.memory_used_mb.toLocaleString()} / ${gpu.memory_total_mb.toLocaleString()} MB` : 'Not reported'} /><MetricCard label="GPU use" value={gpu ? `${gpu.utilization_percent}%` : 'Not reported'} /><MetricCard label="Requests sampled" value={metrics.request_count || 0} /></div>
    </div>
    <div className="subsection"><SectionHeading title="Performance presets" description="Presets apply to a model managed by this application." />
      <div className="catalog-grid">{Object.entries(metrics.presets || {}).map(([name, values]) => <button className="catalog-item" key={name} onClick={() => onPreset(name)} disabled={busy || runtime.managed}><strong>{name.replace('-', ' ')}</strong><span>{Number(values.context_size).toLocaleString()} context · {values.cache_ram_mb} MB cache</span></button>)}</div>
    </div>
  </div>
}
