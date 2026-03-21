import { apiClient } from './client'

export interface Organization {
  id: string
  name: string
  slug: string
  access_status: 'active' | 'suspended' | 'trial' | 'expired'
  users_count: number
  avito_accounts_count: number
  subscription_until: string | null
  suspended_reason: string | null
  created_at: string
}

export interface SystemError {
  id: string
  source: string | null
  layer: string | null
  handler: string | null
  error_type: string | null
  error_message: string
  stack_trace: string | null
  org_id: string | null
  org_name: string | null
  user_id: string | null
  resolved: boolean
  resolved_at: string | null
  note: string | null
  created_at: string
}

export interface SuperAdminStats {
  total_orgs: number
  active_orgs: number
  suspended_orgs: number
  total_users: number
  mailings_today: number
  active_mailings: number
  unresolved_errors: number
  errors_today: number
}

export interface MailingEntry {
  id: string
  org_id: string
  org_name: string | null
  status: string
  total_count: number
  sent_count: number
  created_at: string
}

export const superadminApi = {
  // Organizations
  getOrganizations: (params?: { search?: string; status?: string; page?: number }) =>
    apiClient
      .get<{ items: Organization[] } | Organization[]>('/superadmin/organizations', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  getOrganization: (id: string) =>
    apiClient.get<Organization>(`/superadmin/organizations/${id}`).then(r => r.data),

  createOrganization: (data: {
    name: string
    max_users?: number
    subscription_until?: string
    owner_email?: string
  }) => apiClient.post<Organization>('/superadmin/organizations', data).then(r => r.data),

  updateOrg: (id: string, data: Partial<Organization>) =>
    apiClient
      .patch<Organization>(`/superadmin/organizations/${id}`, data)
      .then(r => r.data),

  suspendOrg: (id: string, reason: string) =>
    apiClient.post(`/superadmin/organizations/${id}/suspend`, { reason }),

  activateOrg: (id: string) =>
    apiClient.post(`/superadmin/organizations/${id}/activate`),

  updateSubscription: (id: string, subscriptionUntil: string | null) =>
    apiClient.patch(`/superadmin/organizations/${id}/subscription`, {
      subscription_until: subscriptionUntil,
    }),

  impersonate: (id: string) =>
    apiClient
      .post<{ access_token: string; refresh_token: string }>(
        `/superadmin/organizations/${id}/impersonate`
      )
      .then(r => r.data),

  // Errors
  getErrors: (params?: {
    org_id?: string
    source?: string
    resolved?: boolean
    page?: number
    limit?: number
  }) =>
    apiClient
      .get<{ items: SystemError[] } | SystemError[]>('/superadmin/errors', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),

  resolveError: (id: string, note?: string) =>
    apiClient.post(`/superadmin/errors/${id}/resolve`, { note }),

  resolveBulk: (ids: string[]) =>
    apiClient.post('/superadmin/errors/resolve-bulk', { ids }),

  // Stats
  getStats: () =>
    apiClient.get<SuperAdminStats>('/superadmin/stats').then(r => r.data),

  // Mailings
  getMailings: (params?: { org_id?: string; status?: string; page?: number }) =>
    apiClient
      .get<{ items: MailingEntry[] } | MailingEntry[]>('/superadmin/mailings', { params })
      .then(r => (Array.isArray(r.data) ? r.data : r.data.items)),
}
