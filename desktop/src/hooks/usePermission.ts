import { useAuthStore } from '@/stores/auth.store'
import type { UserRole } from '@/types/user'

const ROLE_HIERARCHY: Record<UserRole, number> = {
  superadmin: 4,
  owner: 3,
  admin: 2,
  manager: 1,
}

export function useRole(): UserRole {
  return (useAuthStore(s => s.user?.role) ?? 'manager') as UserRole
}

export function useHasRole(minRole: UserRole): boolean {
  const role = useRole()
  return (ROLE_HIERARCHY[role] ?? 0) >= ROLE_HIERARCHY[minRole]
}

export function useIsSuperAdmin(): boolean {
  return useAuthStore(s => s.user?.role === 'superadmin')
}

export function useHasPermission(code: string): boolean {
  const permissions = useAuthStore(s => s.permissions)
  if (permissions === 'all') return true
  if (!permissions) return false
  return permissions.includes(code)
}
