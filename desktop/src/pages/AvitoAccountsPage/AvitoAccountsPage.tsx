import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { avitoAccountsApi, type AvitoAccount } from '@/api/avito-accounts'
import { settingsApi } from '@/api/settings'
import { Table, type Column } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { useUIStore } from '@/stores/ui.store'
import { Plus, RefreshCw, SmartphoneNfc, Trash2, Settings } from 'lucide-react'

const STATUS_CONFIG = {
  active: { label: 'OK', variant: 'success' as const },
  inactive: { label: 'Неактивен', variant: 'default' as const },
  error: { label: 'Ошибка', variant: 'danger' as const },
}

interface AddAccountForm {
  client_id: string
  client_secret: string
}

const defaultForm = (): AddAccountForm => ({
  client_id: '',
  client_secret: '',
})

export default function AvitoAccountsPage() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [showAddModal, setShowAddModal] = useState(false)
  const [form, setForm] = useState<AddAccountForm>(defaultForm())
  const [formErrors, setFormErrors] = useState<Partial<AddAccountForm>>({})
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // Edit department modal
  const [editAccount, setEditAccount] = useState<AvitoAccount | null>(null)
  const [editDepartmentId, setEditDepartmentId] = useState<string>('')

  const { data: accounts, isLoading } = useQuery({
    queryKey: ['avito-accounts'],
    queryFn: () => avitoAccountsApi.getList(),
    staleTime: 60_000,
  })

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: () => settingsApi.getDepartments(),
    staleTime: 5 * 60_000,
  })

  const createAccount = useMutation({
    mutationFn: (data: AddAccountForm) => avitoAccountsApi.create(data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['avito-accounts'] })
      showToast('success', 'Аккаунт подключён')
      setShowAddModal(false)
      setForm(defaultForm())
    },
    onError: () => showToast('error', 'Не удалось подключить аккаунт'),
  })

  const updateAccount = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { department_id: string | null } }) =>
      avitoAccountsApi.update(id, data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['avito-accounts'] })
      showToast('success', 'Настройки сохранены')
      setEditAccount(null)
    },
    onError: () => showToast('error', 'Не удалось сохранить настройки'),
  })

  const refreshBalance = useMutation({
    mutationFn: (id: string) => avitoAccountsApi.refreshBalance(id),
    onSuccess: (data, id) => {
      qc.setQueryData<AvitoAccount[]>(['avito-accounts'], prev =>
        prev?.map(a => (a.id === id ? { ...a, balance: data.balance } : a))
      )
    },
    onError: () => showToast('error', 'Не удалось обновить баланс'),
  })

  const deleteAccount = useMutation({
    mutationFn: (id: string) => avitoAccountsApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['avito-accounts'] })
      showToast('success', 'Аккаунт удалён')
      setDeleteConfirmId(null)
    },
    onError: () => showToast('error', 'Не удалось удалить аккаунт'),
  })

  const validate = (): boolean => {
    const errs: Partial<AddAccountForm> = {}
    if (!form.client_id.trim()) errs.client_id = 'Обязательное поле'
    if (!form.client_secret.trim()) errs.client_secret = 'Обязательное поле'
    setFormErrors(errs)
    return Object.keys(errs).length === 0
  }

  const getDepartmentName = (id: string | null) => {
    if (!id) return '—'
    return departments.find(d => d.id === id)?.name ?? '—'
  }

  const columns: Column<AvitoAccount>[] = [
    {
      key: 'name',
      title: 'Название',
      render: row => <span style={{ fontWeight: 500 }}>{row.name}</span>,
    },
    {
      key: 'department',
      title: 'Отдел',
      render: row => (
        <span style={{ fontSize: 13, color: row.department_id ? 'var(--color-text)' : 'var(--color-text-secondary)' }}>
          {getDepartmentName(row.department_id)}
        </span>
      ),
    },
    {
      key: 'balance',
      title: 'Баланс',
      render: row => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>
            {row.balance != null ? `${row.balance.toLocaleString('ru-RU')} ₽` : '—'}
          </span>
          <button
            title="Обновить баланс"
            onClick={() => refreshBalance.mutate(row.id)}
            style={{
              display: 'flex',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
              padding: 2,
            }}
          >
            <RefreshCw
              size={12}
              style={{
                animation:
                  refreshBalance.isPending && refreshBalance.variables === row.id
                    ? 'spin 0.7s linear infinite'
                    : undefined,
              }}
            />
          </button>
        </div>
      ),
    },
    {
      key: 'webhooks',
      title: 'Вебхуки',
      render: row => (
        <Badge variant={row.webhooks_active ? 'success' : 'default'}>
          {row.webhooks_active ? 'активны' : 'не настроены'}
        </Badge>
      ),
    },
    {
      key: 'status',
      title: 'Статус',
      render: row => (
        <Badge variant={(STATUS_CONFIG[row.status] ?? STATUS_CONFIG['inactive']).variant}>
          {(STATUS_CONFIG[row.status] ?? STATUS_CONFIG['inactive']).label}
        </Badge>
      ),
    },
    {
      key: 'last_sync',
      title: 'Синхронизация',
      render: row =>
        row.last_sync_at
          ? new Date(row.last_sync_at).toLocaleString('ru-RU')
          : '—',
    },
    {
      key: 'actions',
      title: '',
      width: 80,
      align: 'center',
      render: row => (
        <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
          <Button
            variant="ghost"
            size="sm"
            icon={<Settings size={14} />}
            onClick={() => {
              setEditAccount(row)
              setEditDepartmentId(row.department_id ?? '')
            }}
            aria-label="Настроить аккаунт"
          />
          <Button
            variant="ghost"
            size="sm"
            icon={<Trash2 size={14} />}
            onClick={() => setDeleteConfirmId(row.id)}
            aria-label="Удалить аккаунт"
          />
        </div>
      ),
    },
  ]

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Аккаунты Avito</h1>
        <Button icon={<Plus size={15} />} onClick={() => setShowAddModal(true)}>
          Добавить
        </Button>
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
          <Spinner size="lg" />
        </div>
      ) : !accounts?.length ? (
        <EmptyState
          title="Нет подключённых аккаунтов"
          description="Подключите Авито аккаунт для получения сообщений и управления кандидатами"
          icon={<SmartphoneNfc size={40} strokeWidth={1.5} />}
          action={
            <Button icon={<Plus size={15} />} onClick={() => setShowAddModal(true)}>
              Подключить
            </Button>
          }
        />
      ) : (
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
            data={accounts}
            rowKey={row => row.id}
            emptyText="Аккаунтов нет"
          />
        </div>
      )}

      {/* Add account modal */}
      <Modal
        open={showAddModal}
        onClose={() => {
          setShowAddModal(false)
          setForm(defaultForm())
          setFormErrors({})
        }}
        title="Подключить аккаунт Avito"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>
              Отмена
            </Button>
            <Button
              loading={createAccount.isPending}
              onClick={() => {
                if (validate()) createAccount.mutate(form)
              }}
            >
              Подключить
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input
            label="Avito Client ID *"
            placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            value={form.client_id}
            error={formErrors.client_id}
            onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))}
          />
          <Input
            label="Avito Client Secret *"
            type="password"
            placeholder="••••••••••••••••"
            value={form.client_secret}
            error={formErrors.client_secret}
            onChange={e => setForm(f => ({ ...f, client_secret: e.target.value }))}
          />
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
            Название и ID аккаунта будут получены автоматически. После подключения настроятся вебхуки для получения сообщений и откликов.
          </p>
        </div>
      </Modal>

      {/* Edit account modal */}
      <Modal
        open={editAccount !== null}
        onClose={() => setEditAccount(null)}
        title={`Настройки: ${editAccount?.name ?? ''}`}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditAccount(null)}>
              Отмена
            </Button>
            <Button
              loading={updateAccount.isPending}
              onClick={() => {
                if (editAccount) {
                  updateAccount.mutate({
                    id: editAccount.id,
                    data: { department_id: editDepartmentId || null },
                  })
                }
              }}
            >
              Сохранить
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6, color: 'var(--color-text)' }}>
              Отдел для входящих кандидатов
            </label>
            <select
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
              value={editDepartmentId}
              onChange={e => setEditDepartmentId(e.target.value)}
            >
              <option value="">Без отдела</option>
              {departments.map(d => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 6 }}>
              Новые кандидаты с этого аккаунта будут автоматически попадать в выбранный отдел.
            </p>
          </div>
        </div>
      </Modal>

      {/* Delete confirm modal */}
      <Modal
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        title="Удалить аккаунт?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteConfirmId(null)}>
              Отмена
            </Button>
            <Button
              variant="danger"
              loading={deleteAccount.isPending}
              onClick={() => {
                if (deleteConfirmId) deleteAccount.mutate(deleteConfirmId)
              }}
            >
              Удалить
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Аккаунт будет отключён. Сообщения и история переписки сохранятся.
        </p>
      </Modal>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
