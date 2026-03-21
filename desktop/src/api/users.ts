import { apiClient } from './client'
import type { User } from '@/types/user'

export const usersApi = {
  getList: (params?: { page?: number; page_size?: number }) =>
    apiClient
      .get<{ items: User[]; total: number; page: number; pages: number }>('/users', { params })
      .then(r => r.data.items),

  invite: (data: { login_or_email: string; role: string }) =>
    apiClient.post<User>('/users/invite', data).then(r => r.data),

  update: (id: string, data: Partial<Pick<User, 'role' | 'full_name'>>) =>
    apiClient.patch<User>(`/users/${id}`, data).then(r => r.data),

  deactivate: (id: string) =>
    apiClient.delete(`/users/${id}`).then(r => r.data),

  reactivate: (id: string) =>
    apiClient.post(`/users/${id}/reactivate`).then(r => r.data),

  getActivity: (id: string, page = 1) =>
    apiClient
      .get(`/users/${id}/activity`, { params: { page, limit: 50 } })
      .then(r => r.data),

  getPermissions: (id: string) =>
    apiClient.get(`/users/${id}/permissions`).then(r => r.data),

  setPermissions: (
    id: string,
    permissions: Array<{ code: string; granted: boolean }>
  ) => apiClient.put(`/users/${id}/permissions`, { permissions }),

  getDepartments: (id: string) =>
    apiClient.get(`/users/${id}/departments`).then(r => r.data),

  setDepartments: (id: string, departmentIds: string[]) =>
    apiClient.put(`/users/${id}/departments`, { department_ids: departmentIds }),
}
