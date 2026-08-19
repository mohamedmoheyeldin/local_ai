import { useEffect, useState } from 'react'
import { Button, Checkbox, Flash, FormControl, IconButton, TextInput } from '@primer/react'
import { DownloadIcon, FileIcon, ShieldLockIcon, SyncIcon, TrashIcon } from '@primer/octicons-react'
import { DataCard, DeleteButton, EmptyState, Field, FormActions, MetricCard, SectionHeading } from './PrimerUI.jsx'

export function WorkspaceSettings({ workspaces, workspaceRoot, onAdd, onSelect, onDelete, busy }) {
  const [draft, setDraft] = useState({ name: '', path: '' })
  const separator = workspaceRoot?.includes('\\') ? '\\' : '/'
  const normalizedRoot = workspaceRoot?.replace(/[\\/]+$/, '')
  const folderExample = normalizedRoot
    ? `${normalizedRoot}${separator}Projects${separator}my-project`
    : 'Choose a project folder inside your home directory'
  return <div className="settings-section">
    <SectionHeading title="Approved workspaces" description="Only folders you explicitly approve can be used for repository context or Cloud handoff." />
    <form onSubmit={async event => { event.preventDefault(); if (await onAdd(draft)) setDraft({ name: '', path: '' }) }}>
      <div className="form-grid"><Field label="Workspace name" caption="Use a short name you will recognize, such as Work app or Personal project." required><TextInput block value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} placeholder="My project" /></Field><Field label="Project folder" caption="Enter the full path to a folder inside your home directory." required><TextInput block value={draft.path} onChange={event => setDraft({ ...draft, path: event.target.value })} placeholder={folderExample} /></Field></div>
      <FormActions><Button variant="primary" type="submit" disabled={busy}>Approve workspace</Button></FormActions>
    </form>
    <div className="data-list">{workspaces.length === 0 && <EmptyState title="No approved workspaces" description="Add a project folder when you want Local AI to use its files for repository context or Cloud handoff." />}{workspaces.map(item => <DataCard key={item.id} title={item.name} label={item.selected ? 'Selected' : null} meta={item.path} actions={<>{!item.selected && <Button size="small" onClick={() => onSelect(item.id)}>Select</Button>}<DeleteButton onClick={() => onDelete(item.id)} /></>} />)}</div>
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
    <Flash variant="warning" className="privacy-banner"><ShieldLockIcon size={16} /> <strong>The passphrase is optional.</strong> Without one, anyone who gets the backup file can restore its private data and credentials.</Flash>
    <Field label="Backup passphrase" caption="Optional—use any length. A longer unique passphrase provides stronger protection."><TextInput block type="password" value={passphrase} onChange={event => setPassphrase(event.target.value)} autoComplete="new-password" /></Field>
    <FormActions>
      <Button variant="primary" leadingVisual={DownloadIcon} disabled={busy} onClick={() => onBackup(passphrase)}>Download encrypted backup</Button>
      <Button as="label" leadingVisual={FileIcon}>Choose backup<input hidden type="file" accept=".laibak" onChange={event => setRestoreFile(event.target.files?.[0] || null)} /></Button>
      <Button variant="danger" disabled={busy || !restoreFile} onClick={() => onRestore(restoreFile, passphrase)}>Restore and replace</Button>
    </FormActions>
    {restoreFile && <Flash sx={{ mt: 3 }}>Selected: {restoreFile.name}</Flash>}
  </div>
}

function compactBytes(bytes) {
  if (!bytes) return 'Not reported'
  return `${(bytes / 2 ** 30).toFixed(1)} GB`
}

const presetDetails = {
  balanced: { title: 'Balanced', summary: 'A practical default for everyday chat and coding.', best: 'Best for most users', tradeoff: 'Moderate context and memory use' },
  speed: { title: 'Faster responses', summary: 'Keeps context smaller and reserves more prompt cache.', best: 'Best for short, repeated tasks', tradeoff: 'Less room for long conversations' },
  quality: { title: 'Long context', summary: 'Keeps more conversation, documents, and code in one request.', best: 'Best for large projects and documents', tradeoff: 'Uses more RAM or VRAM; prompts may process slower' },
  'low-memory': { title: 'Low memory', summary: 'Minimizes context and cache to reduce resource pressure.', best: 'Best for smaller or busy computers', tradeoff: 'Least room for long instructions and files' },
}

const gpuLevels = [
  { layers: 0, label: 'CPU only' },
  { layers: 16, label: 'Light' },
  { layers: 32, label: 'More' },
  { layers: 9_999, label: 'Maximum' },
]

function SliderSetting({ id, label, value, min, max, step, display, description, onChange, disabled }) {
  return <div className="performance-control">
    <div className="performance-control-heading"><label htmlFor={id}>{label}</label><output htmlFor={id}>{display ?? value}</output></div>
    <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={event => onChange(Number(event.target.value))} disabled={disabled} />
    <p>{description}</p>
  </div>
}

function impactLabel(score) {
  return score >= 72 ? 'High' : score >= 40 ? 'Moderate' : 'Low'
}

function ImpactMeter({ label, score, positive = true }) {
  const normalized = Math.max(0, Math.min(100, Math.round(score)))
  return <div className="impact-meter"><div><span>{label}</span><strong>{impactLabel(normalized)}</strong></div><div className="impact-track" aria-hidden="true"><span className={positive ? 'positive' : 'attention'} style={{ width: `${normalized}%` }} /></div></div>
}

export function PerformanceSettings({ metrics, runtime, settings, hostProfile, onRefresh, onApplyRecommended, onPreset, onSaveCustom, busy }) {
  const gpu = metrics.gpu
  const hostGpu = hostProfile?.gpus?.[0]
  const platform = hostProfile?.platform
  const configuration = hostProfile?.configuration
  const runtimeDependencies = hostProfile ? Object.values(hostProfile.dependencies || {}).filter(item => item.required_at_runtime) : []
  const dependencyCount = runtimeDependencies.filter(item => item.available).length
  const dependencyTotal = runtimeDependencies.length
  const logicalCores = Math.max(1, Math.min(Number(hostProfile?.cpu?.logical_cores) || 16, 64))
  const totalMemoryGb = Math.max(4, (hostProfile?.memory?.total_bytes || 16 * 2 ** 30) / 2 ** 30)
  const maxCache = Math.max(512, Math.min(8_192, 2 ** Math.floor(Math.log2(totalMemoryGb * 128))))
  const [custom, setCustom] = useState({ context_size: 16_384, threads: 8, parallel: 1, cache_ram_mb: 512, gpu_layers: 0, flash_attention: true })
  useEffect(() => {
    setCustom({
      context_size: settings?.context_size ?? 16_384,
      threads: settings?.threads || Math.min(logicalCores, 8),
      parallel: settings?.parallel ?? 1,
      cache_ram_mb: settings?.cache_ram_mb ?? 512,
      gpu_layers: settings?.gpu_layers ?? (hostGpu ? 9_999 : 0),
      flash_attention: settings?.flash_attention ?? true,
    })
  }, [settings, logicalCores, hostGpu])
  const setCustomValue = (key, value) => setCustom(current => ({ ...current, [key]: value }))
  const gpuLevel = custom.gpu_layers >= 9_999 ? 3 : custom.gpu_layers >= 32 ? 2 : custom.gpu_layers > 0 ? 1 : 0
  const contextRatio = (custom.context_size - 2_048) / (65_536 - 2_048)
  const cacheRatio = custom.cache_ram_mb / maxCache
  const threadRatio = custom.threads / logicalCores
  const parallelRatio = (custom.parallel - 1) / 7
  const offloadRatio = gpuLevel / 3
  const responsiveness = 48 + offloadRatio * 34 + cacheRatio * 12 - contextRatio * 16 - parallelRatio * 18
  const memoryPressure = 12 + contextRatio * 46 + cacheRatio * 20 + parallelRatio * 22
  const systemPressure = 10 + threadRatio * 55 + memoryPressure * 0.35
  const changed = ['context_size', 'threads', 'parallel', 'cache_ram_mb', 'gpu_layers', 'flash_attention'].some(key => custom[key] !== settings?.[key])
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
    <div className="subsection"><SectionHeading title="Performance presets" description="Choose a starting point based on what matters most. Presets change resource use and context capacity, not the model's intelligence." />
      <div className="preset-grid">{Object.entries(metrics.presets || {}).map(([name, values]) => {
        const detail = presetDetails[name] || { title: name.replace('-', ' '), summary: 'Provider-defined runtime settings.', best: '', tradeoff: '' }
        return <button className="preset-card" key={name} onClick={() => onPreset(name)} disabled={busy || runtime.managed}><strong>{detail.title}</strong><span>{detail.summary}</span><small>{detail.best}</small><small className="preset-tradeoff">Tradeoff: {detail.tradeoff}</small><code>{Number(values.context_size).toLocaleString()} context · {values.cache_ram_mb} MB cache</code></button>
      })}</div>
    </div>
    <div className="subsection"><SectionHeading title="Custom performance" description="Fine-tune how Local AI uses this computer. Changes apply the next time a model managed by this application starts." />
      <Flash className="privacy-banner"><strong>Impact estimates are directional.</strong> Actual speed and memory use depend on the selected model, prompt, operating system, and hardware. Use Live performance above to compare real results.</Flash>
      <div className="performance-custom-grid">
        <div className="performance-controls">
          <SliderSetting id="custom-context" label="Context window" value={custom.context_size} min={2_048} max={65_536} step={2_048} display={`${custom.context_size.toLocaleString()} tokens`} onChange={value => setCustomValue('context_size', value)} disabled={busy || runtime.managed} description="Higher values keep more conversation, files, and code available, but use more RAM or VRAM and can make prompt processing slower." />
          <SliderSetting id="custom-threads" label="CPU threads" value={Math.min(custom.threads, logicalCores)} min={1} max={logicalCores} step={1} display={`${Math.min(custom.threads, logicalCores)} of ${logicalCores}`} onChange={value => setCustomValue('threads', value)} disabled={busy || runtime.managed} description="More threads can help CPU-based work. Using most cores may make other applications feel less responsive." />
          <SliderSetting id="custom-parallel" label="Parallel requests" value={Math.min(custom.parallel, 8)} min={1} max={8} step={1} display={`${Math.min(custom.parallel, 8)} at once`} onChange={value => setCustomValue('parallel', value)} disabled={busy || runtime.managed} description="More slots allow concurrent requests, but divide memory and compute resources and may reduce single-request speed." />
          <SliderSetting id="custom-cache" label="Prompt cache memory" value={Math.min(custom.cache_ram_mb, maxCache)} min={0} max={maxCache} step={128} display={`${Math.min(custom.cache_ram_mb, maxCache).toLocaleString()} MB`} onChange={value => setCustomValue('cache_ram_mb', value)} disabled={busy || runtime.managed} description="A larger cache can help repeated prompts and shared prefixes, while reserving more system memory." />
          <SliderSetting id="custom-gpu" label="GPU offload" value={gpuLevel} min={0} max={3} step={1} display={hostGpu ? gpuLevels[gpuLevel].label : 'No accelerator detected'} onChange={value => setCustomValue('gpu_layers', gpuLevels[value].layers)} disabled={busy || runtime.managed || !hostGpu} description="More offload usually improves generation speed but consumes more VRAM. Maximum may fail if the model does not fit the GPU." />
          <FormControl><Checkbox id="custom-flash-attention" checked={custom.flash_attention} onChange={event => setCustomValue('flash_attention', event.target.checked)} disabled={busy || runtime.managed} /><FormControl.Label htmlFor="custom-flash-attention">Use flash attention when supported</FormControl.Label><FormControl.Caption>Usually reduces attention memory use and can improve speed. The runtime falls back when unsupported.</FormControl.Caption></FormControl>
        </div>
        <aside className="performance-impact" aria-label="Estimated performance impact">
          <h3>Estimated tradeoffs</h3>
          <p>Higher bars mean more of the named effect. These are comparisons between the slider positions, not benchmark results.</p>
          <ImpactMeter label="Response potential" score={responsiveness} />
          <ImpactMeter label="Long-context capacity" score={contextRatio * 100} />
          <ImpactMeter label="Memory pressure" score={memoryPressure} positive={false} />
          <ImpactMeter label="System resource pressure" score={systemPressure} positive={false} />
          <div className="performance-summary"><strong>{memoryPressure > 72 || systemPressure > 78 ? 'Heavy configuration' : responsiveness > 70 ? 'Speed-focused configuration' : contextRatio > 0.6 ? 'Context-focused configuration' : 'Moderate configuration'}</strong><span>{memoryPressure > 72 ? 'Watch RAM and VRAM use after starting the model.' : systemPressure > 78 ? 'Other applications may receive fewer CPU resources.' : 'A safe starting point for testing on this computer.'}</span></div>
        </aside>
      </div>
      <FormActions><Button onClick={() => setCustom({ context_size: settings.context_size, threads: settings.threads || Math.min(logicalCores, 8), parallel: settings.parallel, cache_ram_mb: settings.cache_ram_mb, gpu_layers: settings.gpu_layers, flash_attention: settings.flash_attention })} disabled={!changed || busy || runtime.managed}>Reset</Button><Button variant="primary" onClick={() => onSaveCustom(custom)} disabled={!changed || busy || runtime.managed}>Save custom performance</Button></FormActions>
    </div>
  </div>
}
