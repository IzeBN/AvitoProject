import { useState, type FormEvent } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { mailingsApi } from '@/api/mailings'
import { useQueryClient } from '@tanstack/react-query'
import { useUIStore } from '@/stores/ui.store'

type TargetMode = 'ids' | 'phones'

interface StartMailingModalProps {
  open: boolean
  onClose: () => void
  preselectedIds?: string[]
}

export const StartMailingModal = ({
  open,
  onClose,
  preselectedIds = [],
}: StartMailingModalProps) => {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const defaultMode: TargetMode = preselectedIds.length > 0 ? 'ids' : 'phones'

  const [mode, setMode] = useState<TargetMode>(defaultMode)
  const [message, setMessage] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [rateLimitMs, setRateLimitMs] = useState(1000)
  const [phonesText, setPhonesText] = useState('')
  const [loading, setLoading] = useState(false)

  const parsedPhones = phonesText
    .split(/[\n,;]+/)
    .map(p => p.trim().replace(/\s/g, ''))
    .filter(p => p.length >= 10)

  const canSubmit =
    message.trim().length > 0 &&
    !loading &&
    (mode === 'ids'
      ? preselectedIds.length > 0
      : mode === 'filters'
      ? true
      : parsedPhones.length > 0)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setLoading(true)
    try {
      if (mode === 'ids') {
        await mailingsApi.startByIds({
          candidate_ids: preselectedIds,
          message: message.trim(),
          scheduled_at: scheduledAt || undefined,
          rate_limit_ms: rateLimitMs,
        })
      } else {
        await mailingsApi.startByPhones({
          phones: parsedPhones,
          message_text: message.trim(),
          scheduled_at: scheduledAt || undefined,
          rate_limit_ms: rateLimitMs,
        })
      }
      await qc.invalidateQueries({ queryKey: ['mailings'] })
      showToast('success', 'Рассылка запущена')
      handleClose()
    } catch {
      showToast('error', 'Не удалось запустить рассылку')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setMessage('')
    setScheduledAt('')
    setPhonesText('')
    setRateLimitMs(1000)
    onClose()
  }

  const MODES: Array<{ id: TargetMode; label: string }> = [
    ...(preselectedIds.length > 0 ? [{ id: 'ids' as TargetMode, label: `Выбранные (${preselectedIds.length})` }] : []),
    { id: 'phones', label: 'По телефонам' },
  ]

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Новая рассылка"
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
        {/* Mode tabs */}
        <div className="smail-tabs">
          {MODES.map(m => (
            <button
              key={m.id}
              type="button"
              className={`smail-tab${mode === m.id ? ' smail-tab--active' : ''}`}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Target description */}
        {mode === 'ids' && (
          <div className="smail-recipients-info">
            <span className="smail-recipients-count">{preselectedIds.length}</span>
            <span className="smail-recipients-label">выбранных кандидатов</span>
          </div>
        )}
        {mode === 'phones' && (
          <div className="smail-field">
            <label className="smail-label">
              Номера телефонов <span className="smail-required">*</span>
            </label>
            <textarea
              className="smail-textarea"
              placeholder={'+7 900 123 45 67\n+7 900 765 43 21\n...'}
              value={phonesText}
              onChange={e => setPhonesText(e.target.value)}
              rows={5}
            />
            {parsedPhones.length > 0 && (
              <span className="smail-hint-small">
                Распознано номеров: <strong>{parsedPhones.length}</strong>
              </span>
            )}
          </div>
        )}

        {/* Message */}
        <div className="smail-field">
          <label className="smail-label" htmlFor="smail-message">
            Текст сообщения <span className="smail-required">*</span>
          </label>
          <textarea
            id="smail-message"
            className="smail-textarea"
            placeholder="Введите текст рассылки..."
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={5}
            required
          />
          <span className="smail-char-count">{message.length} символов</span>
        </div>

        {/* Schedule */}
        <div className="smail-field">
          <label className="smail-label" htmlFor="smail-schedule">Запланировать (опционально)</label>
          <input
            id="smail-schedule"
            type="datetime-local"
            className="smail-input"
            value={scheduledAt}
            onChange={e => setScheduledAt(e.target.value)}
            min={new Date().toISOString().slice(0, 16)}
          />
          {!scheduledAt && (
            <span className="smail-hint-small">Оставьте пустым для немедленной отправки</span>
          )}
        </div>

        {/* Rate */}
        <div className="smail-field">
          <label className="smail-label" htmlFor="smail-rate">
            Задержка между сообщениями: <strong>{rateLimitMs} мс</strong>
          </label>
          <input
            id="smail-rate"
            type="range"
            min={500}
            max={5000}
            step={100}
            value={rateLimitMs}
            onChange={e => setRateLimitMs(Number(e.target.value))}
            className="smail-range"
          />
          <div className="smail-range-labels">
            <span>Быстро (500 мс)</span>
            <span>Медленно (5000 мс)</span>
          </div>
        </div>
      </form>

      <style>{`
        .smail-tabs {
          display: flex;
          gap: 4px;
          background: var(--color-bg);
          border-radius: var(--radius-sm);
          padding: 4px;
        }
        .smail-tab {
          flex: 1;
          padding: 7px 10px;
          font-size: 13px;
          font-weight: 500;
          color: var(--color-text-secondary);
          border-radius: calc(var(--radius-sm) - 2px);
          transition: all 0.15s;
        }
        .smail-tab--active {
          background: var(--color-surface);
          color: var(--color-primary);
          box-shadow: var(--shadow-sm);
        }
        .smail-field { display: flex; flex-direction: column; gap: 6px; }
        .smail-label { font-size: 13px; font-weight: 500; color: var(--color-text); }
        .smail-required { color: var(--color-danger); }
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
        .smail-char-count { font-size: 11px; color: var(--color-text-secondary); text-align: right; }
        .smail-input {
          padding: 8px 12px;
          font-size: 14px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
          transition: border-color 0.15s;
        }
        .smail-input:focus { border-color: var(--color-primary); }
        .smail-hint {
          font-size: 13px;
          color: var(--color-text-secondary);
          padding: 8px 12px;
          background: var(--color-bg);
          border-radius: var(--radius-sm);
          border: 1px solid var(--color-border);
        }
        .smail-hint-small { font-size: 11px; color: var(--color-text-secondary); }
        .smail-range { width: 100%; cursor: pointer; }
        .smail-range-labels {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: var(--color-text-secondary);
        }
        .smail-recipients-info {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          background: #eff6ff;
          border: 1px solid #bfdbfe;
          border-radius: var(--radius-sm);
        }
        .smail-recipients-count { font-size: 20px; font-weight: 700; color: var(--color-primary); }
        .smail-recipients-label { font-size: 14px; color: var(--color-text); }
      `}</style>
    </Modal>
  )
}
