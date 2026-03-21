import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { superadminApi, type SystemError } from '@/api/superadmin'
import { Table, type Column } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { useUIStore } from '@/stores/ui.store'
import { CheckCircle, AlertCircle } from 'lucide-react'

interface ErrorDetailModalProps {
  error: SystemError | null
  onClose: () => void
}

function ErrorDetailModal({ error, onClose }: ErrorDetailModalProps) {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)
  const [note, setNote] = useState('')

  const resolveMutation = useMutation({
    mutationFn: () => superadminApi.resolveError(error!.id, note || undefined),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['superadmin', 'errors'] })
      showToast('success', 'Ошибка отмечена как решённая')
      onClose()
    },
    onError: () => showToast('error', 'Не удалось отметить ошибку'),
  })

  if (!error) return null

  return (
    <Modal
      open
      onClose={onClose}
      title="Детали ошибки"
      size="lg"
      footer={
        !error.resolved ? (
          <>
            <Button variant="secondary" onClick={onClose}>Закрыть</Button>
            <Button
              loading={resolveMutation.isPending}
              onClick={() => resolveMutation.mutate()}
            >
              Отметить решённой
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={onClose}>Закрыть</Button>
        )
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Meta */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {[
            { label: 'Источник', value: error.source ?? '—' },
            { label: 'Слой', value: error.layer ?? '—' },
            { label: 'Обработчик', value: error.handler ?? '—' },
            { label: 'Организация', value: error.org_name ?? error.org_id ?? '—' },
            {
              label: 'Дата',
              value: new Date(error.created_at).toLocaleString('ru-RU'),
            },
            {
              label: 'Статус',
              value: error.resolved ? (
                <Badge variant="success">Решена</Badge>
              ) : (
                <Badge variant="danger">Нерешена</Badge>
              ),
            },
          ].map(row => (
            <div key={row.label}>
              <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 2 }}>
                {row.label}
              </div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{row.value}</div>
            </div>
          ))}
        </div>

        {/* Error message */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
            Сообщение об ошибке
          </div>
          <div
            style={{
              padding: '10px 12px',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: 'var(--radius-sm)',
              fontFamily: 'monospace',
              fontSize: 13,
              color: 'var(--color-danger)',
              wordBreak: 'break-all',
            }}
          >
            {error.error_message}
          </div>
        </div>

        {/* Stack trace */}
        {error.stack_trace && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
              Stack trace
            </div>
            <pre
              style={{
                padding: '10px 12px',
                background: 'var(--color-bg)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                fontFamily: 'monospace',
                fontSize: 11,
                color: 'var(--color-text-secondary)',
                overflow: 'auto',
                maxHeight: 200,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {error.stack_trace}
            </pre>
          </div>
        )}

        {/* Resolve note */}
        {error.resolved && error.note && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
              Заметка при решении
            </div>
            <p style={{ fontSize: 13 }}>{error.note}</p>
          </div>
        )}

        {/* Note input for resolving */}
        {!error.resolved && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
              Заметка (опционально)
            </div>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              rows={2}
              placeholder="Что было сделано..."
              style={{
                width: '100%',
                padding: '8px 12px',
                fontSize: 13,
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
        )}
      </div>
    </Modal>
  )
}

export default function ErrorsTab() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [showResolved, setShowResolved] = useState(false)
  const [sourceFilter, setSourceFilter] = useState('')
  const [selectedError, setSelectedError] = useState<SystemError | null>(null)
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['superadmin', 'errors', showResolved, sourceFilter],
    queryFn: () =>
      superadminApi.getErrors({
        resolved: showResolved ? undefined : false,
        source: sourceFilter || undefined,
        limit: 100,
      }),
    staleTime: 30_000,
  })

  const resolveBulkMutation = useMutation({
    mutationFn: (ids: string[]) => superadminApi.resolveBulk(ids),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['superadmin', 'errors'] })
      showToast('success', `Отмечено решёнными: ${selectedKeys.size}`)
      setSelectedKeys(new Set())
    },
    onError: () => showToast('error', 'Не удалось обновить ошибки'),
  })

  const handleSelectRow = (key: string, checked: boolean) => {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      if (checked) next.add(key)
      else next.delete(key)
      return next
    })
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedKeys(new Set((data ?? []).map(e => e.id)))
    } else {
      setSelectedKeys(new Set())
    }
  }

  const columns: Column<SystemError>[] = [
    {
      key: 'source',
      title: 'Источник',
      width: 90,
      render: row =>
        row.source ? (
          <Badge variant="default">{row.source}</Badge>
        ) : (
          '—'
        ),
    },
    {
      key: 'layer',
      title: 'Слой',
      width: 120,
      render: row => (
        <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--color-text-secondary)' }}>
          {row.layer ?? '—'}
        </span>
      ),
    },
    {
      key: 'message',
      title: 'Ошибка',
      render: row => (
        <span
          style={{
            fontSize: 12,
            fontFamily: 'monospace',
            color: 'var(--color-danger)',
            display: 'block',
            maxWidth: 320,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={row.error_message}
        >
          {row.error_message}
        </span>
      ),
    },
    {
      key: 'org',
      title: 'Организация',
      width: 140,
      render: row => row.org_name ?? row.org_id ?? '—',
    },
    {
      key: 'created_at',
      title: 'Дата',
      width: 140,
      render: row => new Date(row.created_at).toLocaleString('ru-RU'),
    },
    {
      key: 'status',
      title: 'Статус',
      width: 90,
      align: 'center',
      render: row =>
        row.resolved ? (
          <CheckCircle size={16} color="var(--color-success)" />
        ) : (
          <AlertCircle size={16} color="var(--color-danger)" />
        ),
    },
  ]

  // Unique sources for filter
  const sources = [...new Set((data ?? []).map(e => e.source).filter(Boolean))]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <select
          value={sourceFilter}
          onChange={e => setSourceFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="">Все источники</option>
          {sources.map(s => (
            <option key={s} value={s!}>{s}</option>
          ))}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showResolved}
            onChange={e => setShowResolved(e.target.checked)}
            style={{ accentColor: 'var(--color-primary)' }}
          />
          Показать решённые
        </label>
        {selectedKeys.size > 0 && (
          <Button
            size="sm"
            loading={resolveBulkMutation.isPending}
            onClick={() => resolveBulkMutation.mutate([...selectedKeys])}
          >
            Решить выбранные ({selectedKeys.size})
          </Button>
        )}
      </div>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
          <Spinner />
        </div>
      ) : !data?.length ? (
        <EmptyState
          title="Ошибок нет"
          description={showResolved ? 'Нет ошибок' : 'Нерешённых ошибок нет'}
          icon={<CheckCircle size={36} strokeWidth={1.5} />}
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
            data={data}
            rowKey={row => row.id}
            onRowClick={row => setSelectedError(row)}
            selectedKeys={selectedKeys}
            onSelectRow={handleSelectRow}
            onSelectAll={handleSelectAll}
          />
        </div>
      )}

      <ErrorDetailModal error={selectedError} onClose={() => setSelectedError(null)} />
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
}
