import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus, Send } from 'lucide-react'
import { useMailings, usePauseMailing, useCancelMailing, useResumeMailing } from '@/hooks/useMailings'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { MailingCard } from '@/components/mailings/MailingCard'
import { StartMailingModal } from '@/components/mailings/StartMailingModal'
import { useUIStore } from '@/stores/ui.store'
import type { MailingStatus } from '@/types/mailing'

const STATUS_FILTER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'Все' },
  { value: 'running', label: 'Выполняется' },
  { value: 'paused', label: 'Приостановлена' },
  { value: 'done', label: 'Завершена' },
  { value: 'failed', label: 'Ошибка' },
  { value: 'cancelled', label: 'Отменена' },
]

export default function MailingsPage() {
  const [searchParams] = useSearchParams()
  const showToast = useUIStore(s => s.showToast)

  const [statusFilter, setStatusFilter] = useState('')
  const [startModalOpen, setStartModalOpen] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  // Получаем preselected IDs из URL (приходят со страницы кандидатов)
  const preselectedIds = searchParams.get('candidate_ids')?.split(',').filter(Boolean) ?? []

  const { data: mailings = [], isLoading } = useMailings()
  const pauseMailing = usePauseMailing()
  const resumeMailing = useResumeMailing()
  const cancelMailing = useCancelMailing()

  const filtered = statusFilter
    ? mailings.filter(m => m.status === statusFilter as MailingStatus)
    : mailings

  const handlePause = async (id: string) => {
    try {
      await pauseMailing.mutateAsync(id)
      showToast('success', 'Рассылка приостановлена')
    } catch {
      showToast('error', 'Не удалось приостановить рассылку')
    }
  }

  const handleResume = async (id: string) => {
    try {
      await resumeMailing.mutateAsync(id)
      showToast('success', 'Рассылка возобновлена')
    } catch {
      showToast('error', 'Не удалось возобновить рассылку')
    }
  }

  const handleCancel = async (id: string) => {
    if (!confirm('Вы уверены, что хотите отменить рассылку? Это действие нельзя отменить.')) return
    try {
      await cancelMailing.mutateAsync(id)
      showToast('success', 'Рассылка отменена')
    } catch {
      showToast('error', 'Не удалось отменить рассылку')
    }
  }

  return (
    <div className="mlp-page">
      {/* Заголовок */}
      <div className="mlp-header">
        <h1 className="mlp-title">Рассылки</h1>
        <Button
          variant="primary"
          icon={<Plus size={14} />}
          onClick={() => setStartModalOpen(true)}
        >
          Новая рассылка
        </Button>
      </div>

      {/* Фильтр статуса */}
      <div className="mlp-filters">
        <div className="mlp-filter-tabs">
          {STATUS_FILTER_OPTIONS.map(opt => (
            <button
              key={opt.value}
              className={`mlp-filter-tab ${statusFilter === opt.value ? 'mlp-filter-tab--active' : ''}`}
              onClick={() => setStatusFilter(opt.value)}
              type="button"
            >
              {opt.label}
              {opt.value === '' && mailings.length > 0 && (
                <span className="mlp-tab-count">{mailings.length}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Контент */}
      <div className="mlp-body">
        {isLoading ? (
          <div className="mlp-loading">
            <Spinner size="lg" />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="Нет рассылок"
            description={statusFilter ? 'Нет рассылок с таким статусом' : 'Создайте первую рассылку'}
            icon={<Send size={36} strokeWidth={1.5} />}
            action={
              !statusFilter ? (
                <Button icon={<Plus size={14} />} onClick={() => setStartModalOpen(true)}>
                  Новая рассылка
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="mlp-list">
            {filtered.map(job => (
              <MailingCard
                key={job.id}
                job={job}
                onPause={id => void handlePause(id)}
                onResume={id => void handleResume(id)}
                onCancel={id => void handleCancel(id)}
                pauseLoading={pauseMailing.isPending}
                resumeLoading={resumeMailing.isPending}
                cancelLoading={cancelMailing.isPending}
              />
            ))}
          </div>
        )}
      </div>

      {/* Модал создания */}
      <StartMailingModal
        open={startModalOpen || (preselectedIds.length > 0 && !dismissed)}
        onClose={() => { setStartModalOpen(false); setDismissed(true) }}
        preselectedIds={preselectedIds}
      />

      <style>{`
        .mlp-page {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .mlp-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px 24px 16px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          flex-shrink: 0;
        }
        .mlp-title { font-size: 20px; font-weight: 700; }
        .mlp-filters {
          padding: 12px 24px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          flex-shrink: 0;
        }
        .mlp-filter-tabs {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
        }
        .mlp-filter-tab {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 14px;
          border-radius: var(--radius-sm);
          font-size: 13px;
          font-weight: 500;
          color: var(--color-text-secondary);
          border: 1px solid transparent;
          transition: all 0.15s;
        }
        .mlp-filter-tab:hover { background: var(--color-bg); color: var(--color-text); }
        .mlp-filter-tab--active {
          background: var(--color-primary);
          color: #fff;
          border-color: var(--color-primary);
        }
        .mlp-tab-count {
          background: rgba(255,255,255,.3);
          border-radius: 999px;
          padding: 0 6px;
          font-size: 11px;
        }
        .mlp-filter-tab--active .mlp-tab-count { background: rgba(255,255,255,.25); }
        .mlp-body {
          flex: 1;
          overflow-y: auto;
          padding: 20px 24px;
        }
        .mlp-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 80px;
        }
        .mlp-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-width: 800px;
        }
      `}</style>
    </div>
  )
}
