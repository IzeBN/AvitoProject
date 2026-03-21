import { apiClient } from './client'
import type { MailingJob } from '@/types/mailing'

interface StartMailingPayload {
  filters: Record<string, unknown>
  message: string
  scheduled_at?: string
}

export const mailingsApi = {
  getList: () =>
    apiClient
      .get<{ items: MailingJob[] } | MailingJob[]>('/mailings')
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  getOne: (id: string) =>
    apiClient.get<MailingJob>(`/mailings/${id}`).then(r => r.data),

  start: (payload: StartMailingPayload) =>
    apiClient.post<MailingJob>('/mailings', payload).then(r => r.data),

  pause: (id: string) =>
    apiClient.post(`/mailings/${id}/pause`).then(r => r.data),

  resume: (id: string) =>
    apiClient.post(`/mailings/${id}/resume`).then(r => r.data),

  cancel: (id: string) =>
    apiClient.post(`/mailings/${id}/cancel`).then(r => r.data),

  startByIds: (payload: { candidate_ids: string[]; message: string; scheduled_at?: string; rate_limit_ms?: number }) =>
    apiClient.post<MailingJob>('/mailings/by-ids', payload).then(r => r.data),

  startByFilters: (payload: { candidate_filters: Record<string, unknown>; message_text: string; scheduled_at?: string; rate_limit_ms?: number }) =>
    apiClient.post<MailingJob>('/mailings', payload).then(r => r.data),

  startByPhones: (payload: { phones: string[]; message_text: string; scheduled_at?: string; rate_limit_ms?: number }) =>
    apiClient.post<MailingJob>('/mailings/by-phones', payload).then(r => r.data),
}
