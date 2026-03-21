import { create } from 'zustand'

export interface Toast {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
}

interface UIState {
  sidebarCollapsed: boolean
  toasts: Toast[]
  toggleSidebar: () => void
  showToast: (type: Toast['type'], message: string) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  toasts: [],

  toggleSidebar: () =>
    set(s => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  showToast: (type, message) => {
    const id = crypto.randomUUID()
    set(s => ({ toasts: [...s.toasts, { id, type, message }] }))
    setTimeout(
      () => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
      4000
    )
  },

  removeToast: (id) =>
    set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
}))
