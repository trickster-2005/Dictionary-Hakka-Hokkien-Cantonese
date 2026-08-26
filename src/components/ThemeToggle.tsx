import { useTheme } from '../hooks/useTheme'

export function ThemeToggle() {
  const { isDark, toggle } = useTheme()

  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-label="切換淺深色主題">
      {isDark ? '🌙' : '☀️'}
    </button>
  )
}
