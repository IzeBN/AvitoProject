import { apiClient } from './client'

export interface Vacancy {
  id: string
  title: string
  avito_account_id: string | null
  avito_account_name: string | null
  department: { id: string; name: string } | null
  status: 'active' | 'inactive' | 'draft' | 'closed'
  description: string | null
  location: string | null
  created_at: string
}

export const vacanciesApi = {
  create: (data: Omit<Vacancy, 'id' | 'created_at'>) =>
    apiClient.post<Vacancy>('/vacancies', data).then(r => r.data),

  getList: (params?: { status?: string; account_id?: string }) =>
    apiClient
      .get<{ items: Vacancy[] }>('/vacancies', { params })
      .then(r => r.data.items ?? r.data),

  sync: () =>
    apiClient.post<{ synced_count: number }>('/vacancies/sync').then(r => r.data),

  activate: (id: string) =>
    apiClient.post(`/vacancies/${id}/activate`).then(r => r.data),

  deactivate: (id: string) =>
    apiClient.post(`/vacancies/${id}/deactivate`).then(r => r.data),

  update: (id: string, data: Partial<Vacancy>) =>
    apiClient.patch<Vacancy>(`/vacancies/${id}`, data).then(r => r.data),

  exportCsv: () =>
    apiClient
      .get('/vacancies/export', { responseType: 'blob' })
      .then(r => r.data as Blob),
}
