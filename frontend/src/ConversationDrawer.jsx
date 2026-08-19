import { useEffect, useState } from 'react'
import { Button, Dialog, IconButton, TextInput } from '@primer/react'
import { ArchiveIcon, PlusIcon, SearchIcon, TrashIcon } from '@primer/octicons-react'
import { EmptyState } from './PrimerUI.jsx'

export default function ConversationDrawer({ open, onClose, conversations, currentId, onSelect, onNew, onArchive, onDelete, onSearch }) {
  const [query, setQuery] = useState('')
  useEffect(() => { const timer = setTimeout(() => onSearch(query), 180); return () => clearTimeout(timer) }, [query, onSearch])
  if (!open) return null
  return <Dialog title="Conversations" subtitle="Your private local chat history" onClose={onClose} position={{ narrow: 'fullscreen', regular: 'right' }} width="large" height="large">
    <div className="primer-dialog-scroll">
      <Button variant="primary" leadingVisual={PlusIcon} block onClick={() => { onNew(); onClose() }}>New conversation</Button>
      <TextInput aria-label="Search conversations" leadingVisual={SearchIcon} placeholder="Search conversations" value={query} onChange={event => setQuery(event.target.value)} block sx={{ mt: 3 }} />
      <div className="conversation-list">
        {conversations.length === 0 && <EmptyState title="No conversations yet" description="Chats are saved automatically on this computer." />}
        {conversations.map(item => <article className={item.id === currentId ? 'conversation-item active' : 'conversation-item'} key={item.id}>
          <button className="conversation-select" onClick={() => { onSelect(item.id); onClose() }}><strong>{item.title}</strong><span>{item.message_count} message{item.message_count === 1 ? '' : 's'}{item.preview ? ` · ${item.preview}` : ''}</span></button>
          <div className="conversation-actions"><IconButton icon={ArchiveIcon} size="small" variant="invisible" aria-label={`Archive ${item.title}`} onClick={() => onArchive(item.id)} /><IconButton icon={TrashIcon} size="small" variant="invisible" aria-label={`Delete ${item.title}`} onClick={() => onDelete(item.id)} /></div>
        </article>)}
      </div>
    </div>
  </Dialog>
}
