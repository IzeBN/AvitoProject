import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const isWeb = process.env.VITE_MODE === 'web' || process.argv.includes('--mode=web') || process.argv.includes('web')

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: { ignored: ['**/src-tauri/**'] },
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    // web-режим: современные браузеры; tauri: целевая платформа
    target: mode === 'web'
      ? 'es2020'
      : process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'safari13',
    minify: mode === 'web' ? 'esbuild' : (!process.env.TAURI_ENV_DEBUG ? 'esbuild' : false),
    sourcemap: mode !== 'web' && !!process.env.TAURI_ENV_DEBUG,
  },
}))
