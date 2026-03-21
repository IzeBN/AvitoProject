import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { superadminApi, type Organization } from '@/api/superadmin'
import { useAuthStore } from '@/stores/auth.store'
import { Table, type Column } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUIStore } from '@/stores/ui.store'
import { Plus, MoreHorizontal, Search } from 'lucide-react'

type OrgStatus = Organization['access_status']

const STATUS_CONFIG: Record<
  OrgStatus,
  { label: string; variant: 'success' | 'danger' | 'warning' | 'default' }
> = {
  active: { label: 'Активна', variant: 'success' },
  suspended: { label: 'Заморожена', variant: 'danger' },
  trial: { label: 'Пробный', variant: 'warning' },
  expired: { label: 'Истекла', variant: 'default' },
}

interface OrgDetailModalProps {
  org: Organization | null
  onClose: () => void
}

function OrgDetailModal({ org, onClose }: OrgDetailModalProps) {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)
  const setTokens = useAuthStore(s => s.setTokens)

  const [suspendReason, setSuspendReason] = useState('')
  const [subscriptionDate, setSubscriptionDate] = useState(
    org?.subscription_until?.slice(0, 10) ?? ''
  )
  const [action, setAction] = useState<'main' | 'suspend' | 'subscription'>('main')

  const suspendMutation = useMutation({
    mutationFn: () => superadminApi.suspendOrg(org!.id, suspendReason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['superadmin', 'organizations'] })
      showToast('success', 'Организация заморожена')
      onClose()
    },
    onError: () => showToast('error', 'Не удалось заморозить организацию'),
  })

  const activateMutation = useMutation({
    mutationFn: () => superadminApi.activateOrg(org!.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['superadmin', 'organizations'] })
      showToast('success', 'Организация активирована')
      onClose()
    },
    onError: () => showToast('error', 'Не удалось активировать организацию'),
  })

  const subscriptionMutation = useMutation({
    mutationFn: () =>
      superadminApi.updateSubscription(
        org!.id,
        subscriptionDate ? new Date(subscriptionDate).toISOString() : null
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['superadmin', 'organizations'] })
      showToast('success', 'Подписка обновлена')
      setAction('main')
    },
    onError: () => showToast('error', 'Не удалось обновить подписку'),
  })

  const impersonateMutation = useMutation({
    mutationFn: () => superadminApi.impersonate(org!.id),
    onSuccess: async data => {
      await setTokens(data.access_token, data.refresh_token)
      showToast('success', `Вошли как владелец ${org!.name}`)
      onClose()
    },
    onError: () => showToast('error', 'Не удалось войти как владелец'),
  })

  if (!org) return null

  const statusCfg = STATUS_CONFIG[org.access_status]

  return (
    <Modal
      open={org !== null}
      onClose={onClose}
      title={org.name}
      size="md"
      footer={
        action === 'suspend' ? (
          <>
            <Button variant="secondary" onClick={() => setAction('main')}>Назад</Button>
            <Button
              variant="danger"
              loading={suspendMutation.isPending}
              disabled={!suspendReason.trim()}
              onClick={() => suspendMutation.mutate()}
            >
              Заморозить
            </Button>
          </>
        ) : action === 'subscription' ? (
          <>
            <Button variant="secondary" onClick={() => setAction('main')}>Назад</Button>
            <Button
              loading={subscriptionMutation.isPending}
              onClick={() => subscriptionMutation.mutate()}
            >
              Сохранить
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={onClose}>Закрыть</Button>
        )
      }
    >
      {action === 'suspend' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
            Укажите причину заморозки. Она будет сохранена в истории.
          </p>
          <textarea
            autoFocus
            value={suspendReason}
            onChange={e => setSuspendReason(e.target.value)}
            rows={3}
            placeholder="Причина заморозки..."
            style={{
              width: '100%',
              padding: '8px 12px',
              fontSize: 14,
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              resize: 'vertical',
              outline: 'none',
              fontFamily: 'inherit',
            }}
          />
        </div>
      ) : action === 'subscription' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
            Установите дату окончания подписки. Оставьте пустым чтобы убрать ограничение.
          </p>
          <div>
            <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>
              Подписка до
            </label>
            <input
              type="date"
              value={subscriptionDate}
              onChange={e => setSubscriptionDate(e.target.value)}
              style={{
                padding: '8px 12px',
                fontSize: 14,
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                outline: 'none',
              }}
            />
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Info grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {[
              { label: 'Слаг', value: org.slug },
              { label: 'Статус', value: <Badge variant={statusCfg.variant}>{statusCfg.label}</Badge> },
              { label: 'Пользователи', value: String(org.users_count) },
              { label: 'Avito аккаунты', value: String(org.avito_accounts_count) },
              {
                label: 'Подписка до',
                value: org.subscription_until
                  ? new Date(org.subscription_until).toLocaleDateString('ru-RU')
                  : '—',
              },
              {
                label: 'Создана',
                value: new Date(org.created_at).toLocaleDateString('ru-RU'),
              },
            ].map(row => (
              <div key={row.label}>
                <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 2 }}>
                  {row.label}
                </div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{row.value}</div>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              paddingTop: 12,
              borderTop: '1px solid var(--color-border)',
            }}
          >
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAction('subscription')}
            >
              Продлить подписку
            </Button>
            {org.access_status === 'active' ? (
              <Button
                variant="danger"
                size="sm"
                onClick={() => setAction('suspend')}
              >
                Заморозить организацию
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                loading={activateMutation.isPending}
                onClick={() => activateMutation.mutate()}
              >
                Активировать организацию
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              loading={impersonateMutation.isPending}
              onClick={() => impersonateMutation.mutate()}
            >
              Войти как владелец
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}

export default function OrganizationsTab() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({ name: '', max_users: '', owner_email: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['superadmin', 'organizations', search, statusFilter],
    queryFn: () =>
      superadminApi.getOrganizations({
        search: search || undefined,
        status: statusFilter || undefined,
      }),
    staleTime: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      superadminApi.createOrganization({
        name: createForm.name,
        max_users: createForm.max_users ? parseInt(createForm.max_users) : undefined,
        owner_email: createForm.owner_email || undefined,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['superadmin', 'organizations'] })
      showToast('success', 'Организация создана')
      setShowCreateModal(false)
      setCreateForm({ name: '', max_users: '', owner_email: '' })
    },
    onError: () => showToast('error', 'Не удалось создать организацию'),
  })

  const columns: Column<Organization>[] = [
    {
      key: 'name',
      title: 'Название',
      render: row => <span style={{ fontWeight: 500 }}>{row.name}</span>,
    },
    {
      key: 'status',
      title: 'Статус',
      render: row => {
        const cfg = STATUS_CONFIG[row.access_status] ?? { label: row.access_status, variant: 'default' as const }
        return <Badge variant={cfg.variant}>{cfg.label}</Badge>
      },
    },
    {
      key: 'subscription',
      title: 'Подписка',
      render: row =>
        row.subscription_until
          ? `до ${new Date(row.subscription_until).toLocaleDateString('ru-RU')}`
          : '—',
    },
    {
      key: 'users',
      title: 'Юзеры',
      align: 'center',
      render: row => String(row.users_count),
    },
    {
      key: 'created_at',
      title: 'Создана',
      render: row => new Date(row.created_at).toLocaleDateString('ru-RU'),
    },
    {
      key: 'actions',
      title: '',
      width: 48,
      align: 'center',
      render: row => (
        <div style={{ position: 'relative' }}>
          <Button
            variant="ghost"
            size="sm"
            icon={<MoreHorizontal size={16} />}
            onClick={e => {
              e.stopPropagation()
              setMenuOpenId(prev => (prev === row.id ? null : row.id))
            }}
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
              {['Подробнее', 'Редактировать подписку', 'Войти как Owner'].map(label => (
                <button
                  key={label}
                  onClick={() => {
                    setSelectedOrg(row)
                    setMenuOpenId(null)
                  }}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '9px 14px',
                    fontSize: 13,
                    color: 'var(--color-text)',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e =>
                    ((e.target as HTMLElement).style.background = 'var(--color-bg)')
                  }
                  onMouseLeave={e =>
                    ((e.target as HTMLElement).style.background = 'transparent')
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      ),
    },
  ]

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
      onClick={() => setMenuOpenId(null)}
    >
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <Button icon={<Plus size={15} />} size="sm" onClick={() => setShowCreateModal(true)}>
          Создать
        </Button>
        <div style={{ position: 'relative', flex: '0 0 220px' }}>
          <span
            style={{
              position: 'absolute',
              left: 10,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--color-text-secondary)',
              display: 'flex',
            }}
          >
            <Search size={14} />
          </span>
          <input
            type="text"
            placeholder="Поиск..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              width: '100%',
              paddingLeft: 32,
              paddingRight: 12,
              paddingTop: 7,
              paddingBottom: 7,
              fontSize: 13,
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              outline: 'none',
            }}
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{
            padding: '7px 12px',
            fontSize: 13,
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            outline: 'none',
          }}
        >
          <option value="">Все статусы</option>
          <option value="active">Активные</option>
          <option value="suspended">Замороженные</option>
          <option value="trial">Пробный период</option>
          <option value="expired">Истекшие</option>
        </select>
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
          data={data ?? []}
          rowKey={row => row.id}
          loading={isLoading}
          emptyText="Организаций нет"
          onRowClick={row => setSelectedOrg(row)}
        />
      </div>

      <OrgDetailModal org={selectedOrg} onClose={() => setSelectedOrg(null)} />

      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Создать организацию"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
              Отмена
            </Button>
            <Button
              loading={createMutation.isPending}
              disabled={!createForm.name.trim()}
              onClick={() => createMutation.mutate()}
            >
              Создать
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Input
            label="Название организации *"
            placeholder="ООО Вектор"
            value={createForm.name}
            onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
          />
          <Input
            label="Email владельца"
            type="email"
            placeholder="owner@company.com"
            value={createForm.owner_email}
            onChange={e => setCreateForm(f => ({ ...f, owner_email: e.target.value }))}
          />
          <Input
            label="Максимум пользователей"
            type="number"
            placeholder="50"
            value={createForm.max_users}
            onChange={e => setCreateForm(f => ({ ...f, max_users: e.target.value }))}
          />
        </div>
      </Modal>
    </div>
  )
}
