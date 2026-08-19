import { useEffect, useState } from 'react'
import { Button, IconButton, TextInput } from '@primer/react'
import { ArchiveIcon, PlusIcon, SearchIcon, TrashIcon } from '@primer/octicons-react'
import { EmptyState } from './PrimerUI.jsx'

export default function ConversationList({ conversations, currentId, onSelect, onNew, onArchive, onDelete, onSearch, compact = false }) {
  const [query, setQuery] = useState('')
  useEffect(() => { const timer = setTimeout(() => onSearch(query), 180); return () => clearTimeout(timer) }, [query, onSearch])

  return <div className={compact ? 'conversation-browser compact' : 'conversation-browser'}>
    <Button variant="primary" leadingVisual={PlusIcon} block onClick={onNew}>New chat</Button>
    <TextInput aria-label="Search chats" leadingVisual={SearchIcon} placeholder="Search chats" value={query} onChange={event => setQuery(event.target.value)} block />
    <nav className="conversation-list" aria-label="Chat history">
      {conversations.length === 0 && <EmptyState title={query ? 'No matching chats' : 'No chats yet'} description={query ? 'Try a different search.' : 'Start a new chat. It will be saved automatically on this computer.'} />}
      {conversations.map(item => <article className={item.id === currentId ? 'conversation-item active' : 'conversation-item'} key={item.id}>
        <button className="conversation-select" aria-current={item.id === currentId ? 'page' : undefined} onClick={() => onSelect(item.id)}><strong>{item.title}</strong><span>{item.message_count} message{item.message_count === 1 ? '' : 's'}{item.preview ? ` · ${item.preview}` : ''}</span></button>
        <div className="conversation-actions"><IconButton icon={ArchiveIcon} size="small" variant="invisible" aria-label={`Archive ${item.title}`} onClick={() => onArchive(item.id)} /><IconButton icon={TrashIcon} size="small" variant="invisible" aria-label={`Delete ${item.title}`} onClick={() => onDelete(item.id)} /></div>
      </article>)}
    </nav>
  </div>
}
