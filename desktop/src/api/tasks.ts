import { apiClient } from './client'

export interface Task {
  id: string
  org_id: string
  title: string
  description: string | null
  due_date: string | null        // "YYYY-MM-DD"
  status: 'open' | 'in_progress' | 'done'
  priority: 'low' | 'medium' | 'high'
  assignee: { id: string; full_name: string } | null
  candidate: { id: string; name: string | null } | null
  created_at: string
  updated_at: string | null
}

export interface TaskCreatePayload {
  title: string
  description: string | null
  due_date: string | null
  priority: Task['priority']
  status: Task['status']
  responsible_id: string | null
  candidate_id: string | null
}

export const tasksApi = {
  getList: (params?: { status?: string; assignee_id?: string }) =>
    apiClient
      .get<{ items: Task[] } | Task[]>('/tasks', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  create: (data: TaskCreatePayload) =>
    apiClient.post<Task>('/tasks', data).then(r => r.data),

  update: (id: string, data: Partial<TaskCreatePayload>) =>
    apiClient.patch<Task>(`/tasks/${id}`, data).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/tasks/${id}`).then(r => r.data),
}
