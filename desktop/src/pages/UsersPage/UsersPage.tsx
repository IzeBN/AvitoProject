import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { usersApi } from '@/api/users'
import { Table, type Column } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useHasRole } from '@/hooks/usePermission'
import { useUIStore } from '@/stores/ui.store'
import type { User, UserRole } from '@/types/user'
import { UserPlus, MoreHorizontal, Activity } from 'lucide-react'

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Супер-админ',
  owner: 'Владелец',
  admin: 'Администратор',
  manager: 'Менеджер',
}

const SELECTABLE_ROLES: UserRole[] = ['manager', 'admin']

interface InviteForm {
  login_or_email: string
  role: UserRole
}

const defaultInviteForm = (): InviteForm => ({
  login_or_email: '',
  role: 'manager',
})

interface ActivityEntry {
  id: string
  action: string
  entity_type: string | null
  entity_id: string | null
  created_at: string
}

interface ActivityResponse {
  items: ActivityEntry[]
  total: number
}

export default function UsersPage() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)
  const canManage = useHasRole('admin')

  const [showInviteModal, setShowInviteModal] = useState(false)
  const [inviteForm, setInviteForm] = useState<InviteForm>(defaultInviteForm())
  const [inviteSuccess, setInviteSuccess] = useState(false)
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof InviteForm, string>>>({})

  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [activityUserId, setActivityUserId] = useState<string | null>(null)
  const [activityPage, setActivityPage] = useState(1)

  const [changeRoleUserId, setChangeRoleUserId] = useState<string | null>(null)
  const [newRole, setNewRole] = useState<UserRole>('manager')

  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.getList(),
    staleTime: 60_000,
  })

  const { data: activityData, isLoading: activityLoading } = useQuery({
    queryKey: ['users', activityUserId, 'activity', activityPage],
    queryFn: () =>
      usersApi.getActivity(activityUserId!, activityPage) as Promise<ActivityResponse>,
    staleTime: 30_000,
    enabled: activityUserId !== null,
  })

  const inviteMutation = useMutation({
    mutationFn: (data: InviteForm) => usersApi.invite(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      setInviteSuccess(true)
    },
    onError: () => showToast('error', 'Не удалось добавить сотрудника'),
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: UserRole }) =>
      usersApi.update(id, { role }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      showToast('success', 'Роль обновлена')
      setChangeRoleUserId(null)
    },
    onError: () => showToast('error', 'Не удалось изменить роль'),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => usersApi.deactivate(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      showToast('success', 'Пользователь деактивирован')
    },
    onError: () => showToast('error', 'Не удалось деактивировать пользователя'),
  })

  const reactivateMutation = useMutation({
    mutationFn: (id: string) => usersApi.reactivate(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      showToast('success', 'Пользователь активирован')
    },
    onError: () => showToast('error', 'Не удалось активировать пользователя'),
  })

  const validateInviteForm = (): boolean => {
    const errs: Partial<Record<keyof InviteForm, string>> = {}
    if (!inviteForm.login_or_email.trim()) errs.login_or_email = 'Обязательное поле'
    setFormErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleInviteSubmit = () => {
    if (!validateInviteForm()) return
    inviteMutation.mutate(inviteForm)
  }

  const closeInviteModal = () => {
    setShowInviteModal(false)
    setInviteForm(defaultInviteForm())
    setInviteSuccess(false)
    setFormErrors({})
  }

  const activityUser = users?.find(u => u.id === activityUserId)

  const columns: Column<User>[] = [
    {
      key: 'full_name',
      title: 'Имя',
      render: row => (
        <div>
          <div style={{ fontWeight: 500, fontSize: 14 }}>{row.full_name}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{row.email}</div>
        </div>
      ),
    },
    {
      key: 'role',
      title: 'Роль',
      render: row => <Badge variant="default">{ROLE_LABELS[row.role] ?? row.role}</Badge>,
    },
    {
      key: 'is_active',
      title: 'Статус',
      render: row => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: row.is_active ? 'var(--color-success)' : 'var(--color-text-secondary)',
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 13 }}>{row.is_active ? 'Активен' : 'Неактивен'}</span>
        </div>
      ),
    },
    {
      key: 'created_at',
      title: 'Добавлен',
      render: row => new Date(row.created_at).toLocaleDateString('ru-RU'),
    },
    ...(canManage
      ? [
          {
            key: 'actions',
            title: '',
            width: 48,
            align: 'center' as const,
            render: (row: User) => (
              <div style={{ position: 'relative' }}>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<MoreHorizontal size={16} />}
                  onClick={e => {
                    e.stopPropagation()
                    setMenuOpenId(prev => (prev === row.id ? null : row.id))
                  }}
                  aria-label="Действия"
                />
                {menuOpenId === row.id && (
                  <div
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '100%',
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-md)',
                      boxShadow: 'var(--shadow-md)',
                      zIndex: 10,
                      minWidth: 180,
                      overflow: 'hidden',
                    }}
                    onClick={e => e.stopPropagation()}
                  >
                    {[
                      {
                        label: 'Изменить роль',
                        onClick: () => {
                          setNewRole(row.role)
                          setChangeRoleUserId(row.id)
                          setMenuOpenId(null)
                        },
                      },
                      {
                        label: 'История действий',
                        onClick: () => {
                          setActivityUserId(row.id)
                          setActivityPage(1)
                          setMenuOpenId(null)
                        },
                      },
                      {
                        label: row.is_active ? 'Деактивировать' : 'Активировать',
                        danger: row.is_active,
                        onClick: () => {
                          if (row.is_active) deactivateMutation.mutate(row.id)
                          else reactivateMutation.mutate(row.id)
                          setMenuOpenId(null)
                        },
                      },
                    ].map(item => (
                      <button
                        key={item.label}
                        onClick={item.onClick}
                        style={{
                          display: 'block',
                          width: '100%',
                          textAlign: 'left',
                          padding: '9px 14px',
                          fontSize: 13,
                          color: item.danger ? 'var(--color-danger)' : 'var(--color-text)',
                          cursor: 'pointer',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={e =>
                          ((e.target as HTMLElement).style.background = 'var(--color-bg)')
                        }
                        onMouseLeave={e =>
                          ((e.target as HTMLElement).style.background = 'transparent')
                        }
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <div
      style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
      onClick={() => setMenuOpenId(null)}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>
          Сотрудники{users ? ` (${users.length})` : ''}
        </h1>
        {canManage && (
          <Button icon={<UserPlus size={15} />} onClick={() => setShowInviteModal(true)}>
            Добавить
          </Button>
        )}
      </div>

      <div
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
        }}
      >
        <Table
          columns={columns}
          data={users ?? []}
          rowKey={row => row.id}
          loading={isLoading}
          emptyText="Пользователей нет"
        />
      </div>

      {/* Invite modal */}
      <Modal
        open={showInviteModal}
        onClose={closeInviteModal}
        title="Добавить сотрудника"
        size="md"
        footer={
          inviteSuccess ? (
            <Button onClick={closeInviteModal}>Закрыть</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={closeInviteModal}>
                Отмена
              </Button>
              <Button
                loading={inviteMutation.isPending}
                onClick={handleInviteSubmit}
              >
                Добавить
              </Button>
            </>
          )
        }
      >
        {inviteSuccess ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 12,
              padding: '16px 0',
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                background: '#dcfce7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 24,
              }}
            >
              ✓
            </div>
            <p style={{ fontSize: 15, fontWeight: 500 }}>Сотрудник добавлен</p>
            <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', textAlign: 'center' }}>
              Логин: <strong>{inviteForm.login_or_email}</strong>
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Input
              label="Email или логин *"
              placeholder="ivan@company.ru или ivan_petrov"
              value={inviteForm.login_or_email}
              error={formErrors.login_or_email}
              onChange={e => setInviteForm(f => ({ ...f, login_or_email: e.target.value }))}
            />
            <div>
              <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>
                Роль
              </label>
              <select
                value={inviteForm.role}
                onChange={e =>
                  setInviteForm(f => ({ ...f, role: e.target.value as UserRole }))
                }
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: 14,
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  outline: 'none',
                }}
              >
                {SELECTABLE_ROLES.map(r => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </div>
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
              Сотрудник должен быть зарегистрирован в системе заранее.
            </p>
          </div>
        )}
      </Modal>

      {/* Change role modal */}
      <Modal
        open={changeRoleUserId !== null}
        onClose={() => setChangeRoleUserId(null)}
        title="Изменить роль"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setChangeRoleUserId(null)}>
              Отмена
            </Button>
            <Button
              loading={updateRoleMutation.isPending}
              onClick={() => {
                if (changeRoleUserId) {
                  updateRoleMutation.mutate({ id: changeRoleUserId, role: newRole })
                }
              }}
            >
              Сохранить
            </Button>
          </>
        }
      >
        <div>
          <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>
            Новая роль
          </label>
          <select
            value={newRole}
            onChange={e => setNewRole(e.target.value as UserRole)}
            style={{
              width: '100%',
              padding: '8px 12px',
              fontSize: 14,
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              outline: 'none',
            }}
          >
            {SELECTABLE_ROLES.map(r => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </div>
      </Modal>

      {/* Activity modal */}
      <Modal
        open={activityUserId !== null}
        onClose={() => setActivityUserId(null)}
        title={`История действий — ${activityUser?.full_name ?? ''}`}
        size="lg"
      >
        {activityLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
            <Spinner />
          </div>
        ) : !activityData?.items.length ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-secondary)' }}>
            <Activity size={32} strokeWidth={1.5} style={{ margin: '0 auto 8px' }} />
            <p>Действий не найдено</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {activityData.items.map(entry => (
              <div
                key={entry.id}
                style={{
                  display: 'flex',
                  gap: 12,
                  padding: '8px 12px',
                  background: 'var(--color-bg)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 13,
                }}
              >
                <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0, width: 140 }}>
                  {new Date(entry.created_at).toLocaleString('ru-RU')}
                </span>
                <span style={{ color: 'var(--color-text)', flex: 1 }}>
                  {entry.action}
                  {entry.entity_type && (
                    <span style={{ color: 'var(--color-text-secondary)' }}>
                      {' '}· {entry.entity_type}
                      {entry.entity_id && ` #${entry.entity_id.slice(0, 8)}`}
                    </span>
                  )}
                </span>
              </div>
            ))}
            {activityData.total > 50 && (
              <div style={{ textAlign: 'center', paddingTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={activityPage === 1}
                    onClick={() => setActivityPage(p => p - 1)}
                  >
                    Назад
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={activityPage * 50 >= activityData.total}
                    onClick={() => setActivityPage(p => p + 1)}
                  >
                    Вперёд
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
