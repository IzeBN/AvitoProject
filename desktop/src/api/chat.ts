import { apiClient } from './client'
import type { ChatListItem, Message } from '@/types/chat'

export const chatApi = {
  getList: (params?: { search?: string; has_unread?: boolean; avito_account_id?: string }) =>
    apiClient
      .get<ChatListItem[] | { items: ChatListItem[] }>('/chats', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  getMessages: (chatId: string, before?: string) =>
    apiClient
      .get<Message[] | { items: Message[] }>(`/chats/${chatId}/messages`, {
        params: { before, limit: 50 },
      })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  sendMessage: (chatId: string, content: string) =>
    apiClient
      .post<Message>(`/chats/${chatId}/messages`, { content })
      .then(r => r.data),

  markRead: (chatId: string) =>
    apiClient.post(`/chats/${chatId}/read`).then(r => r.data),

  getFastAnswers: () =>
    apiClient.get<Array<{ id: string; title: string; text: string }>>('/fast-answers').then(r => r.data),
}
