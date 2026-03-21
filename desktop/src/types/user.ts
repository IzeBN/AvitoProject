export type UserRole = 'superadmin' | 'owner' | 'admin' | 'manager'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  org_id: string
  is_active: boolean
  created_at: string
}
