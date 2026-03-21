import { useState, type FormEvent } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { mailingsApi } from '@/api/mailings'
import { useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '@/stores/ui.store'
import { useNavigate } from 'react-router-dom'

interface FilterMailingModalProps {
  open: boolean
  onClose: () => void
  filters: Record<string, unknown>
  filtersCount: number
}

export const FilterMailingModal = ({
  open,
  onClose,
  filters,
  filtersCount,
}: FilterMailingModalProps) => {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)
  const navigate = useNavigate()

  const [message, setMessage] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [rateLimitMs, setRateLimitMs] = useState(1000)
  const [loading, setLoading] = useState(false)

  const canSubmit = message.trim().length > 0 && !loading

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    try {
      await mailingsApi.startByFilters({
        candidate_filters: filters,
        message_text: message.trim(),
        scheduled_at: scheduledAt || undefined,
        rate_limit_ms: rateLimitMs,
      })
      await qc.invalidateQueries({ queryKey: ['mailings'] })
      showToast('success', 'Рассылка запущена')
      handleClose()
      navigate('/mailings')
    } catch {
      showToast('error', 'Не удалось запустить рассылку')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setMessage('')
    setScheduledAt('')
    setRateLimitMs(1000)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Рассылка по фильтрам"
      size="md"
      footer={
        <>
          <Button variant="ghost" onClick={handleClose}>Отмена</Button>
          <Button
            onClick={e => void handleSubmit(e as unknown as FormEvent)}
            loading={loading}
            disabled={!canSubmit}
          >
            {scheduledAt ? 'Запланировать' : 'Запустить'}
          </Button>
        </>
      }
    >
      <form onSubmit={e => void handleSubmit(e)} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Info */}
        <div style={{
          padding: '10px 14px',
          background: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: 'var(--radius-sm)',
          fontSize: 13,
          color: 'var(--color-text)',
        }}>
          Рассылка будет отправлена кандидатам по <strong>{filtersCount} активн{filtersCount === 1 ? 'ому фильтру' : 'ым фильтрам'}</strong>
        </div>

        {/* Message */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 500 }}>
            Текст сообщения <span style={{ color: 'var(--color-danger)' }}>*</span>
          </label>
          <textarea
            className="smail-textarea"
            placeholder="Введите текст рассылки..."
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={5}
            required
          />
          <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', textAlign: 'right' }}>
            {message.length} символов
          </span>
        </div>

        {/* Schedule */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 500 }}>Запланировать (опционально)</label>
          <input
            type="datetime-local"
            style={{
              padding: '8px 12px',
              fontSize: 14,
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              outline: 'none',
            }}
            value={scheduledAt}
            onChange={e => setScheduledAt(e.target.value)}
            min={new Date().toISOString().slice(0, 16)}
          />
          {!scheduledAt && (
            <span style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>Оставьте пустым для немедленной отправки</span>
          )}
        </div>

        {/* Rate */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 13, fontWeight: 500 }}>
            Задержка между сообщениями: <strong>{rateLimitMs} мс</strong>
          </label>
          <input
            type="range"
            min={500}
            max={5000}
            step={100}
            value={rateLimitMs}
            onChange={e => setRateLimitMs(Number(e.target.value))}
            style={{ width: '100%', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--color-text-secondary)' }}>
            <span>Быстро (500 мс)</span>
            <span>Медленно (5000 мс)</span>
          </div>
        </div>
      </form>

      <style>{`
        .smail-textarea {
          width: 100%;
          padding: 10px 12px;
          font-size: 14px;
          line-height: 1.5;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          resize: vertical;
          outline: none;
          font-family: inherit;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .smail-textarea:focus {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 3px rgba(59,130,246,.15);
        }
      `}</style>
    </Modal>
  )
}
