import { Pause, Play, X, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { MailingProgress } from './MailingProgress'
import type { MailingJob, MailingStatus } from '@/types/mailing'

interface MailingCardProps {
  job: MailingJob
  onPause: (id: string) => void
  onResume: (id: string) => void
  onCancel: (id: string) => void
  pauseLoading?: boolean
  resumeLoading?: boolean
  cancelLoading?: boolean
}

const statusLabel: Record<MailingStatus, string> = {
  pending: 'Ожидание',
  running: 'Выполняется',
  paused: 'Приостановлена',
  resuming: 'Возобновляется',
  stopping: 'Останавливается',
  done: 'Завершена',
  failed: 'Ошибка',
  cancelled: 'Отменена',
}

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

const formatDateTime = (iso: string | null) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const MailingCard = ({
  job,
  onPause,
  onResume,
  onCancel,
  pauseLoading,
  resumeLoading,
  cancelLoading,
}: MailingCardProps) => {
  const [expanded, setExpanded] = useState(false)

  const isActive = job.status === 'running' || job.status === 'resuming'
  const canPause = job.status === 'running'
  const canResume = job.status === 'paused'
  const canCancel = job.status === 'running' || job.status === 'paused' || job.status === 'pending'

  return (
    <div className={`mcard ${isActive ? 'mcard--active' : ''}`}>
      <div className="mcard-header">
        <div className="mcard-meta">
          <span className="mcard-date">
            Рассылка от {formatDateTime(job.created_at)}
          </span>
          <Badge variant={statusVariant[job.status]}>{statusLabel[job.status]}</Badge>
        </div>
        <button
          className="mcard-expand"
          onClick={() => setExpanded(v => !v)}
          aria-expanded={expanded}
          aria-label={expanded ? 'Свернуть' : 'Развернуть'}
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {job.created_by && (
        <div className="mcard-by">
          Запустил: <strong>{job.created_by.full_name}</strong>
        </div>
      )}

      <MailingProgress job={job} />

      {expanded && (
        <div className="mcard-details">
          <div className="mcard-detail-row">
            <span className="mcard-detail-label">Сообщение:</span>
            <span className="mcard-detail-value">{job.message}</span>
          </div>
          {job.scheduled_at && (
            <div className="mcard-detail-row">
              <span className="mcard-detail-label">Запланировано:</span>
              <span className="mcard-detail-value">{formatDateTime(job.scheduled_at)}</span>
            </div>
          )}
          {job.started_at && (
            <div className="mcard-detail-row">
              <span className="mcard-detail-label">Запущено:</span>
              <span className="mcard-detail-value">{formatDateTime(job.started_at)}</span>
            </div>
          )}
          {job.finished_at && (
            <div className="mcard-detail-row">
              <span className="mcard-detail-label">Завершено:</span>
              <span className="mcard-detail-value">{formatDateTime(job.finished_at)}</span>
            </div>
          )}
        </div>
      )}

      <div className="mcard-actions">
        {canPause && (
          <Button
            variant="secondary"
            size="sm"
            icon={<Pause size={14} />}
            loading={pauseLoading}
            onClick={() => onPause(job.id)}
          >
            Пауза
          </Button>
        )}
        {canResume && (
          <Button
            variant="secondary"
            size="sm"
            icon={<Play size={14} />}
            loading={resumeLoading}
            onClick={() => onResume(job.id)}
          >
            Возобновить
          </Button>
        )}
        {canCancel && (
          <Button
            variant="danger"
            size="sm"
            icon={<X size={14} />}
            loading={cancelLoading}
            onClick={() => onCancel(job.id)}
          >
            Отменить
          </Button>
        )}
      </div>

      <style>{`
        .mcard {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          padding: 16px 20px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          transition: box-shadow 0.2s;
        }
        .mcard--active {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 3px rgba(59,130,246,.08);
        }
        .mcard-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        .mcard-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .mcard-date { font-size: 14px; font-weight: 600; color: var(--color-text); }
        .mcard-expand {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          transition: background 0.15s;
          flex-shrink: 0;
        }
        .mcard-expand:hover { background: var(--color-bg); color: var(--color-text); }
        .mcard-by { font-size: 13px; color: var(--color-text-secondary); }
        .mcard-by strong { color: var(--color-text); }
        .mcard-details {
          background: var(--color-bg);
          border-radius: var(--radius-sm);
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          border: 1px solid var(--color-border);
        }
        .mcard-detail-row {
          display: flex;
          gap: 8px;
          font-size: 13px;
        }
        .mcard-detail-label {
          color: var(--color-text-secondary);
          flex-shrink: 0;
          min-width: 100px;
        }
        .mcard-detail-value {
          color: var(--color-text);
          word-break: break-word;
        }
        .mcard-actions { display: flex; gap: 8px; flex-wrap: wrap; }
      `}</style>
    </div>
  )
}
