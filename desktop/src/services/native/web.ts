import type { NativeService } from './tauri'

export const webNative: NativeService = {
  async getToken(key) {
    return localStorage.getItem(key)
  },

  async setToken(key, value) {
    localStorage.setItem(key, value)
  },

  async clearToken(key) {
    localStorage.removeItem(key)
  },

  async notify(title, body) {
    if (Notification.permission === 'granted') {
      new Notification(title, { body })
    } else if (Notification.permission !== 'denied') {
      const perm = await Notification.requestPermission()
      if (perm === 'granted') new Notification(title, { body })
    }
  },

  async pickFile(extensions) {
    return new Promise(resolve => {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = extensions.map(e => `.${e}`).join(',')
      input.onchange = () => resolve(input.files?.[0] ?? null)
      input.click()
    })
  },

  async saveFile(data, defaultName) {
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = defaultName
    a.click()
    URL.revokeObjectURL(url)
  },
}
