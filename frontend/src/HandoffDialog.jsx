import { useEffect, useState } from 'react'
import { Dialog, Flash, FormControl, Select, Spinner, Text, TextInput, Textarea } from '@primer/react'
import { api } from './api.js'

export default function HandoffDialog({ open, onClose, messages, runtime, workspaces, conversationId }) {
  const [repoPath, setRepoPath] = useState('')
  const [workspaceId, setWorkspaceId] = useState('')
  const [result, setResult] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  useEffect(() => { if (open) setWorkspaceId(workspaces.find(item => item.selected)?.id || workspaces[0]?.id || '') }, [open, workspaces])
  if (!open) return null
  async function prepare() {
    setBusy(true); setNotice(''); setResult('')
    try { const data = await api('/api/cloud-handoff', { method: 'POST', body: JSON.stringify({ messages, repo_path: repoPath, workspace_id: workspaceId || null, conversation_id: conversationId }) }); setResult(data.package) }
    catch (error) { setNotice(error.message) } finally { setBusy(false) }
  }
  async function copy() { await navigator.clipboard.writeText(result); setNotice('Handoff copied to clipboard') }
  const footerButtons = [
    { content: 'Cancel', onClick: onClose },
    result ? { buttonType: 'primary', content: 'Copy handoff', onClick: copy } : { buttonType: 'primary', content: busy ? 'Preparing…' : 'Prepare with Local AI', onClick: prepare, disabled: busy || !runtime.healthy || messages.length === 0 },
  ]
  return <Dialog title="Cloud handoff" subtitle="Local-first, focused escalation package" onClose={onClose} position={{ narrow: 'fullscreen', regular: 'center' }} width="xlarge" height="large" footerButtons={footerButtons}>
    <div className="primer-dialog-scroll">
      <Text as="p" sx={{ color: 'fg.muted', mt: 0 }}>Your local model selects and summarizes useful evidence before you copy anything to a cloud agent.</Text>
      {workspaces.length > 0 && <FormControl sx={{ mt: 3 }}><FormControl.Label>Approved workspace</FormControl.Label><Select block value={workspaceId} onChange={event => { setWorkspaceId(Number(event.target.value)); setRepoPath('') }}>{workspaces.map(item => <Select.Option value={item.id} key={item.id}>{item.name} · {item.path}</Select.Option>)}</Select></FormControl>}
      <FormControl sx={{ mt: 3 }}><FormControl.Label>Repository folder</FormControl.Label><TextInput block value={repoPath} onChange={event => { setRepoPath(event.target.value); if (event.target.value) setWorkspaceId('') }} placeholder="Optional absolute project path" /><FormControl.Caption>An approved workspace is preferred.</FormControl.Caption></FormControl>
      {notice && <Flash variant={notice.includes('copied') ? 'success' : 'danger'} sx={{ mt: 3 }}>{notice}</Flash>}
      {busy && <Flash sx={{ mt: 3 }}><Spinner size="small" sx={{ mr: 2 }} /> Preparing a concise package with Local AI…</Flash>}
      {result && <FormControl sx={{ mt: 3 }}><FormControl.Label>Review before copying</FormControl.Label><Textarea className="handoff-preview" value={result} onChange={event => setResult(event.target.value)} resize="vertical" /></FormControl>}
    </div>
  </Dialog>
}
