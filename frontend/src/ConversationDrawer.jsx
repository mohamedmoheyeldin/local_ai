import { Dialog } from '@primer/react'
import ConversationList from './ConversationList.jsx'

export default function ConversationDrawer({ open, onClose, conversations, currentId, onSelect, onNew, onArchive, onDelete, onSearch }) {
  if (!open) return null
  return <Dialog title="Chats" subtitle="Your private local chat history" onClose={onClose} position={{ narrow: 'fullscreen', regular: 'left' }} width="large" height="large">
    <div className="primer-dialog-scroll">
      <ConversationList conversations={conversations} currentId={currentId} onSelect={id => { onSelect(id); onClose() }} onNew={() => { onNew(); onClose() }} onArchive={onArchive} onDelete={onDelete} onSearch={onSearch} />
    </div>
  </Dialog>
}
