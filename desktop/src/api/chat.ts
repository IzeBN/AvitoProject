import { apiClient } from './client'
import type { ChatListItem, Message } from '@/types/chat'

export const chatApi = {
  getList: (params?: { search?: string; has_unread?: boolean; avito_account_id?: string }) =>
    apiClient
      .get<ChatListItem[] | { items: ChatListItem[] }>('/chat/list', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

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
}
