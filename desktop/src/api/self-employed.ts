import { apiClient } from './client'

export interface SelfEmployedCheckResult {
  inn: string
  is_active: boolean
  registration_date: string | null
  checked_at: string
}

export interface SelfEmployedHistoryEntry {
  id: string
  inn: string
  is_active: boolean
  checked_at: string
  checked_by: string | null
}

export interface SelfEmployedHistoryResponse {
  items: SelfEmployedHistoryEntry[]
  total: number
  page: number
  total_pages: number
}

export const selfEmployedApi = {
  check: (inn: string) =>
    apiClient
      .post<SelfEmployedCheckResult>('/self-employed/check', { inn })
      .then(r => r.data),

  checkBulk: (inns: string[]) =>
    apiClient
      .post<SelfEmployedCheckResult[]>('/self-employed/check-bulk', { inns })
      .then(r => r.data),

  getHistory: (page = 1) =>
    apiClient
      .get<SelfEmployedHistoryResponse>('/self-employed/history', { params: { page } })
      .then(r => r.data),
}
