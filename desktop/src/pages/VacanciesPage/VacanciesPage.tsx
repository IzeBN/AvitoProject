import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { vacanciesApi, type Vacancy } from '@/api/vacancies'
import { avitoAccountsApi } from '@/api/avito-accounts'
import { Table, type Column } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useUIStore } from '@/stores/ui.store'
import { RefreshCw, Download, ChevronDown } from 'lucide-react'

const STATUS_CONFIG: Record<
  Vacancy['status'],
  { label: string; variant: 'success' | 'default' | 'warning' | 'danger' }
> = {
  active: { label: 'Активна', variant: 'success' },
  inactive: { label: 'Снята', variant: 'default' },
  draft: { label: 'Черновик', variant: 'warning' },
  closed: { label: 'Закрыта', variant: 'danger' },
}

export default function VacanciesPage() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [statusFilter, setStatusFilter] = useState<string>('')
  const [accountFilter, setAccountFilter] = useState<string>('')
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  const { data: vacancies, isLoading } = useQuery({
    queryKey: ['vacancies', statusFilter, accountFilter],
    queryFn: () =>
      vacanciesApi.getList({
        status: statusFilter || undefined,
        account_id: accountFilter || undefined,
      }),
    staleTime: 60_000,
  })

  const { data: accounts } = useQuery({
    queryKey: ['avito-accounts'],
    queryFn: () => avitoAccountsApi.getList(),
    staleTime: 120_000,
  })

  const syncMutation = useMutation({
    mutationFn: () => vacanciesApi.sync(),
    onSuccess: data => {
      void qc.invalidateQueries({ queryKey: ['vacancies'] })
      showToast('success', `Синхронизировано ${data.synced_count} вакансий`)
    },
    onError: () => showToast('error', 'Ошибка синхронизации'),
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => vacanciesApi.activate(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['vacancies'] })
      showToast('success', 'Вакансия опубликована')
    },
    onError: () => showToast('error', 'Не удалось опубликовать вакансию'),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => vacanciesApi.deactivate(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['vacancies'] })
      showToast('success', 'Вакансия снята')
    },
    onError: () => showToast('error', 'Не удалось снять вакансию'),
  })

  const handleExportCsv = async () => {
    try {
      const blob = await vacanciesApi.exportCsv()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `vacancies-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      showToast('error', 'Не удалось экспортировать вакансии')
    }
  }

  const columns: Column<Vacancy>[] = [
    {
      key: 'title',
      title: 'Название',
      render: row => <span style={{ fontWeight: 500 }}>{row.title}</span>,
    },
    {
      key: 'account',
      title: 'Аккаунт',
      render: row => row.avito_account_name ?? '—',
    },
    {
      key: 'location',
      title: 'Город',
      render: row => row.location ?? '—',
    },
    {
      key: 'status',
      title: 'Статус',
      render: row => {
        const cfg = STATUS_CONFIG[row.status]
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background:
                  row.status === 'active'
                    ? 'var(--color-success)'
                    : 'var(--color-text-secondary)',
                flexShrink: 0,
              }}
            />
            <Badge variant={cfg.variant}>{cfg.label}</Badge>
          </div>
        )
      },
    },
    {
      key: 'created_at',
      title: 'Добавлена',
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
            icon={<ChevronDown size={14} />}
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
                minWidth: 160,
                overflow: 'hidden',
              }}
              onClick={e => e.stopPropagation()}
            >
              {row.status !== 'active' && (
                <ActionMenuItem
                  label="Опубликовать"
                  onClick={() => {
                    activateMutation.mutate(row.id)
                    setMenuOpenId(null)
                  }}
                />
              )}
              {row.status === 'active' && (
                <ActionMenuItem
                  label="Снять с публикации"
                  danger
                  onClick={() => {
                    deactivateMutation.mutate(row.id)
                    setMenuOpenId(null)
                  }}
                />
              )}
            </div>
          )}
        </div>
      ),
    },
  ]

  return (
    <div
      style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}
      onClick={() => setMenuOpenId(null)}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Вакансии</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            variant="secondary"
            icon={<RefreshCw size={14} />}
            loading={syncMutation.isPending}
            onClick={() => syncMutation.mutate()}
          >
            Синхронизировать
          </Button>
          <Button
            variant="secondary"
            icon={<Download size={14} />}
            onClick={() => void handleExportCsv()}
          >
            Экспорт CSV
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <select
          value={accountFilter}
          onChange={e => setAccountFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="">Все аккаунты</option>
          {accounts?.map(acc => (
            <option key={acc.id} value={acc.id}>
              {acc.name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="">Все статусы</option>
          <option value="active">Активные</option>
          <option value="inactive">Снятые</option>
          <option value="draft">Черновики</option>
          <option value="closed">Закрытые</option>
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
          data={vacancies ?? []}
          rowKey={row => row.id}
          loading={isLoading}
          emptyText="Вакансий нет"
        />
      </div>
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '7px 12px',
  fontSize: 13,
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-sm)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  outline: 'none',
  cursor: 'pointer',
}

function ActionMenuItem({
  label,
  onClick,
  danger = false,
}: {
  label: string
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        padding: '9px 14px',
        fontSize: 13,
        color: danger ? 'var(--color-danger)' : 'var(--color-text)',
        cursor: 'pointer',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => ((e.target as HTMLElement).style.background = 'var(--color-bg)')}
      onMouseLeave={e => ((e.target as HTMLElement).style.background = 'transparent')}
    >
      {label}
    </button>
  )
}
