import { apiClient } from './client'
import type { Candidate, CandidateFilters } from '@/types/candidate'

interface CandidatesListResponse {
  items: Candidate[]
  total: number
  pages: number
}

export const candidatesApi = {
  getList: (filters: CandidateFilters, page = 1, pageSize = 50) =>
    apiClient
      .get<CandidatesListResponse>('/candidates', {
        params: { ...filters, page, page_size: pageSize },
      })
      .then(r => r.data),

  getOne: (id: string) =>
    apiClient.get<Candidate>(`/candidates/${id}`).then(r => r.data),

  update: (id: string, data: Partial<Candidate>) =>
    apiClient
      .patch<Candidate>(`/candidates/${id}`, data)
      .then(r => r.data),

  bulkEdit: (candidateIds: string[], edit: Record<string, unknown>) =>
    apiClient
      .post('/candidates/bulk-edit', { candidate_ids: candidateIds, edit })
      .then(r => r.data),

  addTag: (id: string, tagId: string) =>
    apiClient.post(`/candidates/${id}/tags/${tagId}`).then(r => r.data),

  removeTag: (id: string, tagId: string) =>
    apiClient.delete(`/candidates/${id}/tags/${tagId}`).then(r => r.data),

  getHistory: (id: string) =>
    apiClient.get(`/candidates/${id}/history`).then(r => r.data),

  create: (data: { full_name: string; phone?: string }) =>
    apiClient.post<Candidate>('/candidates', data).then(r => r.data),

  exportCsv: () =>
    apiClient.get('/candidates/export', { responseType: 'blob' }).then(r => r.data as Blob),
}
