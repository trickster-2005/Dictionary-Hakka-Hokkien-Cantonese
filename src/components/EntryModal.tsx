import { EntryCard } from './EntryCard'
import type { Entry } from '../types'

interface Props {
  entry: Entry
  favorited: boolean
  onToggleFavorite: () => void
  onClose: () => void
}

export function EntryModal({ entry, favorited, onToggleFavorite, onClose }: Props) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose} aria-label="關閉">
          ✕
        </button>
        <EntryCard entry={entry} favorited={favorited} onToggleFavorite={onToggleFavorite} showLangLabel />
      </div>
    </div>
  )
}
