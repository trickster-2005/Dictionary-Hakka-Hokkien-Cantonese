interface Props {
  history: string[]
  onSelect: (term: string) => void
  onClear: () => void
}

export function SearchHistoryChips({ history, onSelect, onClear }: Props) {
  if (history.length === 0) return null

  return (
    <div className="history-chips">
      <span className="history-chips__label">最近查詢:</span>
      {history.map((term) => (
        <button key={term} type="button" className="history-chip" onClick={() => onSelect(term)}>
          {term}
        </button>
      ))}
      <button type="button" className="history-chips__clear" onClick={onClear}>
        清除
      </button>
    </div>
  )
}
