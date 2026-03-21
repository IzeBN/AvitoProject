import { useQuery } from '@tanstack/react-query'
import { mailingsApi } from '@/api/mailings'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import type { MailingStatus } from '@/types/mailing'

const statusVariant: Record<MailingStatus, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'default',
  running: 'info',
  paused: 'warning',
  resuming: 'info',
  stopping: 'warning',
  done: 'success',
  failed: 'danger',
  cancelled: 'default',
}

export default function MailingsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['superadmin', 'mailings'],
    queryFn: () => mailingsApi.getList(),
    staleTime: 30_000,
  })

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
  }

  if (!data?.length) {
    return <EmptyState title="Рассылок нет" />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map(job => (
        <div
          key={job.id}
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
          }}
        >
          <Badge variant={statusVariant[job.status]}>{job.status}</Badge>
          <span style={{ flex: 1, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {job.message}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
            {job.sent}/{job.total}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
            {job.created_by.full_name}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
            {new Date(job.created_at).toLocaleString('ru-RU')}
          </span>
        </div>
      ))}
    </div>
  )
}
