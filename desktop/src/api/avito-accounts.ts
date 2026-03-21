import { apiClient } from './client'

export interface AvitoAccount {
  id: string
  name: string
  avito_user_id: string
  avito_client_id: string | null
  status: 'active' | 'inactive' | 'error'
  balance: number | null
  webhooks_active: boolean
  unread_count: number
  last_sync_at: string | null
  department_id: string | null
}

export const avitoAccountsApi = {
  getList: () =>
    apiClient.get<AvitoAccount[]>('/avito-accounts').then(r => r.data),

  create: (data: {
    client_id: string
    client_secret: string
  }) => apiClient.post<AvitoAccount>('/avito-accounts', data).then(r => r.data),

  update: (id: string, data: { account_name?: string; department_id?: string | null }) =>
    apiClient.patch<AvitoAccount>(`/avito-accounts/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/avito-accounts/${id}`).then(r => r.data),

  sync: (id: string) =>
    apiClient.post(`/avito-accounts/${id}/sync`).then(r => r.data),

  setupWebhooks: (id: string) =>
    apiClient.post(`/avito-accounts/${id}/setup-webhooks`).then(r => r.data),

  refreshBalance: (id: string) =>
    apiClient
      .post<{ balance: number }>(`/avito-accounts/${id}/refresh-balance`)
      .then(r => r.data),
}
