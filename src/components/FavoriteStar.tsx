interface Props {
  active: boolean
  onToggle: () => void
}

export function FavoriteStar({ active, onToggle }: Props) {
  return (
    <button
      type="button"
      className={`favorite-star${active ? ' favorite-star--active' : ''}`}
      onClick={onToggle}
      aria-pressed={active}
      aria-label={active ? '取消收藏' : '加入收藏'}
    >
      {active ? '★' : '☆'}
    </button>
  )
}
