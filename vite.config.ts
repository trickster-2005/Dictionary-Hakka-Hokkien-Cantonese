import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// GitHub Pages serves this as a project site under /Dictionary-Hakka-Hokkien-Cantonese/,
// not the domain root — only applied to production builds so local dev stays at "/".
// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/Dictionary-Hakka-Hokkien-Cantonese/' : '/',
  plugins: [react()],
}))
