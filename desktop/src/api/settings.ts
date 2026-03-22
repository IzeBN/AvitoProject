import { apiClient } from './client'

export interface Stage {
  id: string
  name: string
  color: string | null
  order: number
  is_default?: boolean
}

export interface Tag {
  id: string
  name: string
  color: string | null
}

export interface Department {
  id: string
  name: string
  description: string | null
}

export const settingsApi = {
  // Этапы
  getStages: () =>
    apiClient.get<Stage[]>('/settings/stages').then(r => r.data),
  createStage: (data: Omit<Stage, 'id'>) =>
    apiClient.post<Stage>('/settings/stages', data).then(r => r.data),
  updateStage: (id: string, data: Partial<Stage>) =>
    apiClient.patch<Stage>(`/settings/stages/${id}`, data).then(r => r.data),
  deleteStage: (id: string) =>
    apiClient.delete(`/settings/stages/${id}`).then(r => r.data),
  reorderStages: (ids: string[]) =>
    apiClient.post('/settings/stages/reorder', { ids }).then(r => r.data),
  setDefaultStage: (id: string) =>
    apiClient.post(`/candidates/stages/${id}/set-default`).then(r => r.data),

  // Теги
  getTags: () =>
    apiClient.get<Tag[]>('/settings/tags').then(r => r.data),
  createTag: (data: Omit<Tag, 'id'>) =>
    apiClient.post<Tag>('/settings/tags', data).then(r => r.data),
  updateTag: (id: string, data: Partial<Tag>) =>
    apiClient.patch<Tag>(`/settings/tags/${id}`, data).then(r => r.data),
  deleteTag: (id: string) =>
    apiClient.delete(`/settings/tags/${id}`).then(r => r.data),

  // Отделы
  getDepartments: () =>
    apiClient.get<Department[]>('/settings/departments').then(r => r.data),
  createDepartment: (data: Omit<Department, 'id'>) =>
    apiClient.post<Department>('/settings/departments', data).then(r => r.data),
  updateDepartment: (id: string, data: Partial<Department>) =>
    apiClient
      .patch<Department>(`/settings/departments/${id}`, data)
      .then(r => r.data),
  deleteDepartment: (id: string) =>
    apiClient.delete(`/settings/departments/${id}`).then(r => r.data),

  // Org settings
  getOrgSettings: () =>
    apiClient.get<{ auto_tag_id: string | null }>('/settings/org').then(r => r.data),
  updateOrgSettings: (data: { auto_tag_id: string | null }) =>
    apiClient.put('/settings/org', data).then(r => r.data),

  // Role permissions
  getRolePermissions: (role: string) =>
    apiClient.get(`/settings/role-permissions/${role}`).then(r => r.data),

  setRolePermissions: (role: string, permissionCodes: string[]) =>
    apiClient
      .put(`/settings/role-permissions/${role}`, { permission_codes: permissionCodes })
      .then(r => r.data),
}
