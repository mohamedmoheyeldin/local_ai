import { useRef } from 'react'
import { ActionList, ActionMenu, IconButton } from '@primer/react'
import { FileDirectoryIcon, FileIcon, PaperclipIcon, TrashIcon } from '@primer/octicons-react'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

export default function AttachmentMenu({ sources, indexing, disabled, onPick, onRemove }) {
  const filesRef = useRef(null)
  const folderRef = useRef(null)
  function selected(event, folder = false) {
    const files = Array.from(event.target.files || [])
    event.target.value = ''
    if (!files.length) return
    onPick(files, files.map(file => folder ? file.webkitRelativePath || file.name : file.name))
  }
  return <>
    {sources.length > 0 && <div className="context-tray" aria-label="Attached and indexed context">
      {sources.map(source => <div className="context-chip" key={source.id} title={source.relative_path}>
        <FileIcon size={14} /><span><strong>{source.relative_path}</strong><small>{formatSize(source.size_bytes)} · {source.chunk_count} chunks</small></span>
        <IconButton unsafeDisableTooltip icon={TrashIcon} size="small" variant="invisible" aria-label={`Remove ${source.relative_path}`} onClick={() => onRemove(source)} disabled={indexing} />
      </div>)}
    </div>}
    <ActionMenu>
      <ActionMenu.Button aria-label="Add files or folders" leadingVisual={PaperclipIcon} disabled={disabled || indexing}><span className="attach-label">{indexing ? 'Indexing…' : 'Add context'}</span></ActionMenu.Button>
      <ActionMenu.Overlay align="start"><ActionList>
        <ActionList.Item onSelect={() => filesRef.current?.click()}><ActionList.LeadingVisual><FileIcon /></ActionList.LeadingVisual>Files<ActionList.Description variant="block">Select one or more local files</ActionList.Description></ActionList.Item>
        <ActionList.Item onSelect={() => folderRef.current?.click()}><ActionList.LeadingVisual><FileDirectoryIcon /></ActionList.LeadingVisual>Folder<ActionList.Description variant="block">Index supported files in a folder</ActionList.Description></ActionList.Item>
      </ActionList></ActionMenu.Overlay>
    </ActionMenu>
    <input ref={filesRef} className="visually-hidden" tabIndex={-1} type="file" multiple onChange={event => selected(event)} />
    <input ref={folderRef} className="visually-hidden" tabIndex={-1} type="file" multiple webkitdirectory="" directory="" onChange={event => selected(event, true)} />
  </>
}
