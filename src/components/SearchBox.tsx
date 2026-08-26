interface Props {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
}

export function SearchBox({ value, onChange, onSubmit }: Props) {
  return (
    <form
      className="search-box"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="輸入華語詞彙，例如：今天"
        aria-label="華語詞彙搜尋"
      />
      <button type="submit">查詢</button>
    </form>
  )
}
