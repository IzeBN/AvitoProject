import { useState, useEffect, useRef, Fragment } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { settingsApi } from '@/api/settings'
import { Spinner } from '@/components/ui/Spinner'
import { useUIStore } from '@/stores/ui.store'

type Role = 'manager' | 'admin'

interface PermissionDef {
  code: string
  label: string
  group: string
}

const PERMISSIONS: PermissionDef[] = [
  { code: 'crm.candidates.view', label: 'Просмотр кандидатов', group: 'CRM' },
  { code: 'crm.candidates.edit', label: 'Редактирование кандидатов', group: 'CRM' },
  { code: 'crm.candidates.delete', label: 'Удаление кандидатов', group: 'CRM' },
  { code: 'crm.stages.manage', label: 'Управление этапами', group: 'CRM' },
  { code: 'mailing.view', label: 'Просмотр рассылок', group: 'Рассылки' },
  { code: 'mailing.send', label: 'Отправка рассылок', group: 'Рассылки' },
  { code: 'mailing.manage', label: 'Управление шаблонами', group: 'Рассылки' },
  { code: 'vacancies.view', label: 'Просмотр вакансий', group: 'Вакансии' },
  { code: 'vacancies.manage', label: 'Управление вакансиями', group: 'Вакансии' },
  { code: 'messaging.view', label: 'Просмотр сообщений', group: 'Сообщения' },
  { code: 'messaging.send', label: 'Отправка сообщений', group: 'Сообщения' },
  { code: 'messaging.auto_response', label: 'Автоответы', group: 'Сообщения' },
  { code: 'self_employed.check', label: 'Проверка самозанятых', group: 'Самозанятые' },
  { code: 'analytics.view', label: 'Просмотр аналитики', group: 'Аналитика' },
]

const ROLES: { id: Role; label: string }[] = [
  { id: 'manager', label: 'Менеджер' },
  { id: 'admin', label: 'Администратор' },
]

const GROUPS = [...new Set(PERMISSIONS.map(p => p.group))]

interface RolePermissionsResponse {
  permission_codes: string[]
}

function PermissionsMatrix() {
  const showToast = useUIStore(s => s.showToast)

  const [localCodes, setLocalCodes] = useState<Record<Role, Set<string>>>({
    manager: new Set(),
    admin: new Set(),
  })
  const [initialized, setInitialized] = useState<Record<Role, boolean>>({
    manager: false,
    admin: false,
  })
  const debounceTimers = useRef<Record<Role, ReturnType<typeof setTimeout> | null>>({
    manager: null,
    admin: null,
  })

  const managerQuery = useQuery({
    queryKey: ['settings', 'role-permissions', 'manager'],
    queryFn: () => settingsApi.getRolePermissions('manager') as Promise<RolePermissionsResponse>,
    staleTime: 60_000,
  })

  const adminQuery = useQuery({
    queryKey: ['settings', 'role-permissions', 'admin'],
    queryFn: () => settingsApi.getRolePermissions('admin') as Promise<RolePermissionsResponse>,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (managerQuery.data && !initialized.manager) {
      setLocalCodes(prev => ({ ...prev, manager: new Set(managerQuery.data.permission_codes) }))
      setInitialized(prev => ({ ...prev, manager: true }))
    }
  }, [managerQuery.data, initialized.manager])

  useEffect(() => {
    if (adminQuery.data && !initialized.admin) {
      setLocalCodes(prev => ({ ...prev, admin: new Set(adminQuery.data.permission_codes) }))
      setInitialized(prev => ({ ...prev, admin: true }))
    }
  }, [adminQuery.data, initialized.admin])

  const saveMutation = useMutation({
    mutationFn: ({ role, codes }: { role: Role; codes: string[] }) =>
      settingsApi.setRolePermissions(role, codes),
    onError: (_err, vars) =>
      showToast('error', `Не удалось сохранить права роли ${vars.role}`),
  })

  const toggle = (role: Role, code: string) => {
    setLocalCodes(prev => {
      const next = new Set(prev[role])
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return { ...prev, [role]: next }
    })

    if (debounceTimers.current[role]) clearTimeout(debounceTimers.current[role]!)
    debounceTimers.current[role] = setTimeout(() => {
      setLocalCodes(current => {
        saveMutation.mutate({ role, codes: [...current[role]] })
        return current
      })
    }, 500)
  }

  if (managerQuery.isLoading || adminQuery.isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
        <Spinner />
      </div>
    )
  }

  if (managerQuery.isError || adminQuery.isError) {
    return (
      <div style={{ color: 'var(--color-danger)', padding: 16, fontSize: 14 }}>
        Не удалось загрузить настройки прав
      </div>
    )
  }

  return (
    <div
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: 'var(--color-bg)' }}>
            <th
              style={{
                padding: '10px 16px',
                textAlign: 'left',
                fontSize: 12,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--color-text-secondary)',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              Право
            </th>
            {ROLES.map(r => (
              <th
                key={r.id}
                style={{
                  padding: '10px 24px',
                  textAlign: 'center',
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--color-text-secondary)',
                  borderBottom: '1px solid var(--color-border)',
                  width: 140,
                }}
              >
                {r.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {GROUPS.map(group => (
            <Fragment key={group}>
              <tr>
                <td
                  colSpan={ROLES.length + 1}
                  style={{
                    padding: '7px 16px',
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: 'var(--color-text-secondary)',
                    background: 'var(--color-bg)',
                    borderBottom: '1px solid var(--color-border)',
                    borderTop: '1px solid var(--color-border)',
                  }}
                >
                  {group}
                </td>
              </tr>
              {PERMISSIONS.filter(p => p.group === group).map((perm, idx, arr) => (
                <tr
                  key={perm.code}
                  style={{
                    borderBottom:
                      idx < arr.length - 1 ? '1px solid var(--color-border)' : undefined,
                  }}
                >
                  <td style={{ padding: '10px 16px', color: 'var(--color-text)' }}>
                    <span>{perm.label}</span>
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 11,
                        color: 'var(--color-text-secondary)',
                        fontFamily: 'monospace',
                      }}
                    >
                      {perm.code}
                    </span>
                  </td>
                  {ROLES.map(r => (
                    <td key={r.id} style={{ padding: '10px 24px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={localCodes[r.id].has(perm.code)}
                        onChange={() => toggle(r.id, perm.code)}
                        style={{
                          width: 16,
                          height: 16,
                          cursor: 'pointer',
                          accentColor: 'var(--color-primary)',
                        }}
                        aria-label={`${perm.label} для роли ${r.label}`}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      <div
        style={{
          padding: '10px 16px',
          fontSize: 12,
          color: 'var(--color-text-secondary)',
          borderTop: '1px solid var(--color-border)',
        }}
      >
        Изменения сохраняются автоматически с задержкой 0.5 с. Права владельца и
        супер-администратора не редактируются здесь.
      </div>
    </div>
  )
}

export default function PermissionsSettings() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Матрица прав ролей</h2>
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
          Настройте какие действия доступны менеджерам и администраторам вашей организации.
        </p>
      </div>
      <PermissionsMatrix />
    </div>
  )
}
