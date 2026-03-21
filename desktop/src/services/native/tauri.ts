import { invoke } from '@tauri-apps/api/core'
import { sendNotification } from '@tauri-apps/plugin-notification'
import { open } from '@tauri-apps/plugin-dialog'

export interface NativeService {
  getToken(key: string): Promise<string | null>
  setToken(key: string, value: string): Promise<void>
  clearToken(key: string): Promise<void>
  notify(title: string, body: string): Promise<void>
  pickFile(extensions: string[]): Promise<File | null>
  saveFile(data: Blob, defaultName: string): Promise<void>
}

export const tauriNative: NativeService = {
  async getToken(key) {
    return invoke<string | null>('get_token', { key })
  },

  async setToken(key, value) {
    await invoke('set_token', { key, value })
  },

  async clearToken(key) {
    await invoke('clear_token', { key })
  },

  async notify(title, body) {
    await sendNotification({ title, body })
  },

  async pickFile(extensions) {
    const result = await open({
      filters: [{ name: 'Files', extensions }],
    })
    if (!result || Array.isArray(result)) return null
    // Tauri возвращает путь к файлу, читаем через asset:// протокол
    const resp = await fetch(`asset://${result}`)
    const blob = await resp.blob()
    const name = result.split('/').pop() ?? 'file'
    return new File([blob], name)
  },

  async saveFile(data, defaultName) {
    // Используем стандартный браузерный download (работает в WebView)
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = defaultName
    a.click()
    URL.revokeObjectURL(url)
  },
}
