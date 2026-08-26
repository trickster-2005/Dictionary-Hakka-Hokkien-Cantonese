import type { HakkaVariant } from '../types'

interface Props {
  value: HakkaVariant
  onChange: (value: HakkaVariant) => void
}

export function HakkaVariantSelect({ value, onChange }: Props) {
  return (
    <select
      className="hakka-variant-select"
      value={value}
      onChange={(e) => onChange(e.target.value as HakkaVariant)}
      aria-label="客語腔調"
    >
      <option value="hailu">海陸腔</option>
      <option value="sixian">四縣腔</option>
    </select>
  )
}
