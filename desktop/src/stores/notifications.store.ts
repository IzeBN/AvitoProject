import { create } from 'zustand'

export interface AppNotification {
  id: string
  type: 'task_assigned'
  title: string
  body: string
  task_id?: string
  read: boolean
  created_at: string
}

interface NotificationsState {
  notifications: AppNotification[]
  unread: number
  add: (n: Omit<AppNotification, 'id' | 'read' | 'created_at'>) => void
  markAllRead: () => void
  clear: () => void
}

export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  notifications: [],
  unread: 0,

  add: (n) => {
    const notification: AppNotification = {
      ...n,
      id: crypto.randomUUID(),
      read: false,
      created_at: new Date().toISOString(),
    }
    set(s => ({
      notifications: [notification, ...s.notifications].slice(0, 50),
      unread: s.unread + 1,
    }))
  },

  markAllRead: () =>
    set(s => ({
      notifications: s.notifications.map(n => ({ ...n, read: true })),
      unread: 0,
    })),

  clear: () => set({ notifications: [], unread: 0 }),
}))
