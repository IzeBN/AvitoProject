import { apiClient } from './client'
import type { ChatListItem, Message } from '@/types/chat'

interface ChatFilterOptions {
  stages: Array<{ id: string; name: string; color: string | null }>
  tags: Array<{ id: string; name: string; color: string | null }>
  departments: Array<{ id: string; name: string }>
  responsible_users: Array<{ id: string; full_name: string }>
  avito_accounts: Array<{ id: string; name: string }>
}

export const chatApi = {
  getList: (params?: {
    search?: string
    has_unread?: boolean
    avito_account_id?: string
    stage_id?: string
    responsible_id?: string
  }) =>
    apiClient
      .get<ChatListItem[] | { items: ChatListItem[] }>('/chat/list', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  getFilters: () =>
    apiClient.get<ChatFilterOptions>('/chat/filters').then(r => r.data),

  getMessages: (candidateId: string, before?: string) =>
    apiClient
      .get<Message[] | { items: Message[] }>(`/chat/${candidateId}/messages`, {
        params: { before_id: before, limit: 50 },
      })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  sendMessage: (candidateId: string, content: string) =>
    apiClient
      .post<Message>(`/chat/${candidateId}/send`, { text: content })
      .then(r => r.data),

  markRead: (candidateId: string) =>
    apiClient.post(`/chat/${candidateId}/read`).then(r => r.data),

  getFastAnswers: () =>
    apiClient.get<Array<{ id: string; title: string; text: string }>>('/chat/fast-answers').then(r => r.data),

  syncChat: (candidateId: string) =>
    apiClient.post<{ added: number }>(`/chat/${candidateId}/sync`).then(r => r.data),
}
