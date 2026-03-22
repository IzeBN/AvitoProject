import { apiClient } from './client'

export interface AutoResponseRule {
  id: string
  avito_account_id: string
  avito_account_name: string | null
  avito_item_ids: number[] | null
  message: string | null
  auto_type: 'on_message' | 'on_response' | null
  is_active: boolean
}

export interface DefaultMessage {
  avito_account_id: string
  avito_account_name: string | null
  message: string
}

export interface ItemMessage {
  avito_item_id: number
  avito_account_id: string
  message: string
}

export interface FastAnswer {
  id: string
  message: string
  order: number
}

export const autoResponseApi = {
  // Rules
  getRules: () =>
    apiClient.get<AutoResponseRule[]>('/messaging/auto-response').then(r => r.data),

  createRule: (data: {
    avito_account_id: string
    avito_item_ids?: number[]
    message?: string
    auto_type?: string
  }) => apiClient.post<AutoResponseRule>('/messaging/auto-response', data).then(r => r.data),

  updateRule: (id: string, data: { is_active?: boolean; auto_type?: string; message?: string; avito_item_ids?: number[] }) =>
    apiClient
      .patch<AutoResponseRule>(`/messaging/auto-response/${id}`, data)
      .then(r => r.data),

  deleteRule: (id: string) =>
    apiClient.delete(`/messaging/auto-response/${id}`).then(r => r.data),

  // Default messages
  getDefaultMessages: () =>
    apiClient.get<DefaultMessage[]>('/messaging/default').then(r => r.data),

  setDefaultMessage: (accountId: string, message: string) =>
    apiClient.put(`/messaging/default/${accountId}`, { message }).then(r => r.data),

  // Item messages
  getItemMessages: () =>
    apiClient.get<ItemMessage[]>('/messaging/items').then(r => r.data),

  setItemMessage: (itemId: number, data: { message: string; avito_account_id: string }) =>
    apiClient.put(`/messaging/items/${itemId}`, data).then(r => r.data),

  // Fast answers
  getFastAnswers: () =>
    apiClient.get<FastAnswer[]>('/messaging/fast-answers').then(r => r.data),

  createFastAnswer: (message: string) =>
    apiClient.post<FastAnswer>('/messaging/fast-answers', { message }).then(r => r.data),

  updateFastAnswer: (id: string, message: string) =>
    apiClient
      .patch<FastAnswer>(`/messaging/fast-answers/${id}`, { message })
      .then(r => r.data),

  deleteFastAnswer: (id: string) =>
    apiClient.delete(`/messaging/fast-answers/${id}`).then(r => r.data),

  reorderFastAnswers: (ids: string[]) =>
    apiClient.put('/messaging/fast-answers/reorder', { ids }).then(r => r.data),
}
