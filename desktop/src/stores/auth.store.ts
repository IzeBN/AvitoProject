import { create } from 'zustand'
import { native } from '@/services/native'

interface AuthUser {
  id: string
  email: string
  role: string
  org_id: string | null
  org_name: string | null
  full_name: string
}

interface AuthState {
  accessToken: string | null
  user: AuthUser | null
  /** true пока идёт загрузка токена из хранилища при старте */
  initializing: boolean
  /** null — не загружены, 'all' — все права (owner/superadmin), string[] — список кодов */
  permissions: string[] | 'all' | null
  setTokens: (access: string, refresh: string) => Promise<void>
  refresh: () => Promise<string>
  logout: () => Promise<void>
  loadFromStorage: () => Promise<void>
  loadPermissions: () => Promise<void>
}

function decodeJwtPayload(token: string): AuthUser {
  const payload = JSON.parse(atob(token.split('.')[1]))
  return payload as AuthUser
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  initializing: true,
  permissions: null,

  async setTokens(access, refresh) {
    await native.setToken('access_token', access)
    await native.setToken('refresh_token', refresh)
    const user = decodeJwtPayload(access)
    set({ accessToken: access, user, permissions: null })
    await get().loadPermissions()
  },

  async refresh() {
    const refreshToken = await native.getToken('refresh_token')
    if (!refreshToken) throw new Error('No refresh token')
    const { default: axios } = await import('axios')
    const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
    const { data } = await axios.post<{
      access_token: string
      refresh_token: string
    }>(`${base}/auth/refresh`, { refresh_token: refreshToken })
    await get().setTokens(data.access_token, data.refresh_token)
    return data.access_token
  },

  async logout() {
    await native.clearToken('access_token')
    await native.clearToken('refresh_token')
    set({ accessToken: null, user: null, permissions: null })
  },

  async loadPermissions() {
    const token = get().accessToken
    if (!token) return
    try {
      const { default: axios } = await import('axios')
      const base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
      const { data } = await axios.get<{ all: boolean; granted: string[] }>(
        `${base}/users/me/permissions`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      set({ permissions: data.all ? 'all' : data.granted })
    } catch {
      set({ permissions: [] })
    }
  },

  async loadFromStorage() {
    if (get().accessToken) {
      set({ initializing: false })
      return
    }
    try {
      const token = await native.getToken('access_token')
      if (!token) return

      const raw = JSON.parse(atob(token.split('.')[1])) as { exp?: number }
      if (raw.exp && raw.exp * 1000 > Date.now()) {
        const user = decodeJwtPayload(token)
        set({ accessToken: token, user })
        await get().loadPermissions()
      } else {
        await get().refresh()
      }
    } catch {
      await get().logout()
    } finally {
      set({ initializing: false })
    }
  },
}))
