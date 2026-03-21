import { useState, useEffect } from 'react'
import { X, MessageCircle, Clock, User, Building2, Tag, Calendar, FileText, Briefcase } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { useCandidate, useUpdateCandidate } from '@/hooks/useCandidates'
import { candidatesApi } from '@/api/candidates'
import { vacanciesApi } from '@/api/vacancies'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { StageSelect } from './StageSelect'
import { useUIStore } from '@/stores/ui.store'
import type { Candidate } from '@/types/candidate'

const VacancyField = ({ vacancy, onUpdate }: { vacancy: string | null | undefined; onUpdate: (v: string | null) => void }) => {
  const { data: vacancies = [] } = useQuery({
    queryKey: ['vacancies'],
    queryFn: () => vacanciesApi.getList(),
    staleTime: 60_000,
  })
  return (
    <div className="cmodal-field">
      <div className="cmodal-field-label">
        <Briefcase size={14} />
        Вакансия
      </div>
      <select
        className="cmodal-select"
        value={vacancy ?? ''}
        onChange={e => onUpdate(e.target.value || null)}
      >
        <option value="">Не указана</option>
        {vacancies.map((v: { id: string; title: string }) => (
          <option key={v.id} value={v.title}>{v.title}</option>
        ))}
      </select>
    </div>
  )
}

interface HistoryEntry {
  id: string
  field: string
  old_value: string | null
  new_value: string | null
  changed_by: string
  changed_at: string
}

interface FilterOption {
  id: string
  name: string
  color?: string | null
}

interface CandidateModalProps {
  candidateId: string | null
  onClose: () => void
  onOpenChat: (candidate: Candidate) => void
  stages: FilterOption[]
  responsibles: FilterOption[]
  departments: FilterOption[]
  tags: FilterOption[]
}

export const CandidateModal = ({
  candidateId,
  onClose,
  onOpenChat,
  stages,
  responsibles,
  departments,
  tags,
}: CandidateModalProps) => {
  const { data: candidate, isLoading } = useCandidate(candidateId ?? '')
  const updateCandidate = useUpdateCandidate()
  const showToast = useUIStore(s => s.showToast)

  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [comment, setComment] = useState('')
  const [editingComment, setEditingComment] = useState(false)

  useEffect(() => {
    if (!candidateId) return
    setHistoryLoading(true)
    candidatesApi
      .getHistory(candidateId)
      .then((data: HistoryEntry[]) => setHistory(data.slice(0, 10)))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false))
  }, [candidateId])

  useEffect(() => {
    if (candidate?.comment !== undefined) {
      setComment(candidate.comment ?? '')
    }
  }, [candidate?.comment])

  const handleUpdate = async (field: string, value: unknown) => {
    if (!candidateId) return
    try {
      await updateCandidate.mutateAsync({ id: candidateId, data: { [field]: value } })
      showToast('success', 'Изменения сохранены')
    } catch {
      showToast('error', 'Не удалось сохранить изменения')
    }
  }

  const handleAddTag = async (tagId: string) => {
    if (!candidateId) return
    try {
      await candidatesApi.addTag(candidateId, tagId)
      await updateCandidate.mutateAsync({ id: candidateId, data: {} })
      showToast('success', 'Тег добавлен')
    } catch {
      showToast('error', 'Не удалось добавить тег')
    }
  }

  const handleRemoveTag = async (tagId: string) => {
    if (!candidateId) return
    try {
      await candidatesApi.removeTag(candidateId, tagId)
      await updateCandidate.mutateAsync({ id: candidateId, data: {} })
      showToast('success', 'Тег удалён')
    } catch {
      showToast('error', 'Не удалось удалить тег')
    }
  }

  const saveComment = () => {
    void handleUpdate('comment', comment)
    setEditingComment(false)
  }

  const fieldLabel: Record<string, string> = {
    stage_id: 'Этап',
    responsible_id: 'Ответственный',
    department_id: 'Отдел',
    comment: 'Комментарий',
    due_date: 'Дедлайн',
  }

  if (!candidateId) return null

  return createPortal(
    <div className="cmodal-overlay" onClick={onClose}>
      <aside className="cmodal" onClick={e => e.stopPropagation()} aria-label="Карточка кандидата">
        <div className="cmodal-header">
          <div className="cmodal-title-row">
            {isLoading ? (
              <Spinner size="sm" />
            ) : (
              <h2 className="cmodal-title">{candidate?.name ?? 'Кандидат'}</h2>
            )}
            {candidate?.phone && (
              <span className="cmodal-phone">{candidate.phone}</span>
            )}
          </div>
          <div className="cmodal-header-actions">
            {candidate && (
              <Button
                variant="primary"
                size="sm"
                icon={<MessageCircle size={14} />}
                onClick={() => onOpenChat(candidate)}
              >
                Открыть чат
              </Button>
            )}
            <button className="cmodal-close" onClick={onClose} aria-label="Закрыть">
              <X size={18} />
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="cmodal-loading">
            <Spinner size="lg" />
          </div>
        ) : candidate ? (
          <div className="cmodal-body">
            {/* Этап */}
            <div className="cmodal-field">
              <div className="cmodal-field-label">
                <GitBranchIcon />
                Этап
              </div>
              <StageSelect
                stages={stages.map(s => ({ id: s.id, name: s.name, color: s.color ?? null }))}
                value={candidate.stage?.id ?? ''}
                onChange={e => void handleUpdate('stage_id', e.target.value || null)}
              />
            </div>

            {/* Ответственный */}
            <div className="cmodal-field">
              <div className="cmodal-field-label">
                <User size={14} />
                Ответственный
              </div>
              <select
                className="cmodal-select"
                value={candidate.responsible?.id ?? ''}
                onChange={e => void handleUpdate('responsible_id', e.target.value || null)}
              >
                <option value="">Не назначен</option>
                {responsibles.map(r => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </div>

            {/* Отдел */}
            <div className="cmodal-field">
              <div className="cmodal-field-label">
                <Building2 size={14} />
                Отдел
              </div>
              <select
                className="cmodal-select"
                value={candidate.department?.id ?? ''}
                onChange={e => void handleUpdate('department_id', e.target.value || null)}
              >
                <option value="">Не указан</option>
                {departments.map(d => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>

            {/* Дедлайн */}
            <div className="cmodal-field">
              <div className="cmodal-field-label">
                <Calendar size={14} />
                Дедлайн
              </div>
              <input
                type="date"
                className="cmodal-date"
                value={candidate.due_date ? candidate.due_date.split('T')[0] : ''}
                onChange={e => void handleUpdate('due_date', e.target.value || null)}
              />
            </div>

            {/* Вакансия */}
            <VacancyField vacancy={candidate.vacancy} onUpdate={v => void handleUpdate('vacancy', v)} />

            {/* Теги */}
            <div className="cmodal-field cmodal-field--tags">
              <div className="cmodal-field-label">
                <Tag size={14} />
                Теги
              </div>
              <div className="cmodal-tags">
                {candidate.tags.map(tag => (
                  <span key={tag.id} className="cmodal-tag">
                    <Badge color={tag.color ?? undefined}>{tag.name}</Badge>
                    <button
                      className="cmodal-tag-remove"
                      onClick={() => void handleRemoveTag(tag.id)}
                      aria-label={`Удалить тег ${tag.name}`}
                    >
                      <X size={10} />
                    </button>
                  </span>
                ))}
                <select
                  className="cmodal-tag-add"
                  value=""
                  onChange={e => {
                    if (e.target.value) void handleAddTag(e.target.value)
                  }}
                >
                  <option value="">+ Тег</option>
                  {tags
                    .filter(t => !candidate.tags.some(ct => ct.id === t.id))
                    .map(t => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                </select>
              </div>
            </div>

            {/* Комментарий */}
            <div className="cmodal-field cmodal-field--comment">
              <div className="cmodal-field-label">
                <FileText size={14} />
                Комментарий
              </div>
              {editingComment ? (
                <div className="cmodal-comment-edit">
                  <textarea
                    className="cmodal-textarea"
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    rows={3}
                    autoFocus
                    onKeyDown={e => {
                      if (e.key === 'Enter' && e.ctrlKey) saveComment()
                      if (e.key === 'Escape') setEditingComment(false)
                    }}
                  />
                  <div className="cmodal-comment-actions">
                    <Button size="sm" onClick={saveComment} loading={updateCandidate.isPending}>
                      Сохранить
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingComment(false)}>
                      Отмена
                    </Button>
                  </div>
                </div>
              ) : (
                <button
                  className="cmodal-comment-view"
                  onClick={() => setEditingComment(true)}
                  title="Нажмите для редактирования"
                >
                  {comment || <span style={{ color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>Добавить комментарий...</span>}
                </button>
              )}
            </div>

            {/* История изменений */}
            <div className="cmodal-history">
              <h3 className="cmodal-history-title">История изменений</h3>
              {historyLoading ? (
                <Spinner size="sm" />
              ) : history.length === 0 ? (
                <p className="cmodal-history-empty">Изменений нет</p>
              ) : (
                <ul className="cmodal-history-list">
                  {history.map(entry => (
                    <li key={entry.id} className="cmodal-history-item">
                      <div className="cmodal-history-meta">
                        <span className="cmodal-history-field">{fieldLabel[entry.field] ?? entry.field}</span>
                        <span className="cmodal-history-who">{entry.changed_by}</span>
                        <span className="cmodal-history-when">
                          {new Date(entry.changed_at).toLocaleString('ru-RU', {
                            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                          })}
                        </span>
                      </div>
                      <div className="cmodal-history-change">
                        {entry.old_value && (
                          <span className="cmodal-history-old">{entry.old_value}</span>
                        )}
                        {entry.old_value && <span style={{ color: 'var(--color-text-secondary)' }}>→</span>}
                        <span className="cmodal-history-new">{entry.new_value ?? '—'}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : null}

        <style>{`
          .cmodal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,.3);
            z-index: 900;
            display: flex;
            justify-content: flex-end;
          }
          .cmodal {
            width: 420px;
            height: 100%;
            background: var(--color-surface);
            box-shadow: var(--shadow-md);
            display: flex;
            flex-direction: column;
            animation: slideInRight 0.2s ease;
            overflow: hidden;
          }
          @keyframes slideInRight {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
          .cmodal-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            padding: 20px 20px 16px;
            border-bottom: 1px solid var(--color-border);
            flex-shrink: 0;
            gap: 12px;
          }
          .cmodal-title-row {
            display: flex;
            flex-direction: column;
            gap: 4px;
          }
          .cmodal-title { font-size: 18px; font-weight: 700; }
          .cmodal-phone { font-size: 13px; color: var(--color-text-secondary); }
          .cmodal-header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-shrink: 0;
          }
          .cmodal-close {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border-radius: var(--radius-sm);
            color: var(--color-text-secondary);
            transition: background 0.15s;
          }
          .cmodal-close:hover { background: var(--color-bg); color: var(--color-text); }
          .cmodal-loading {
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1;
          }
          .cmodal-body {
            flex: 1;
            overflow-y: auto;
            padding: 16px 20px;
            display: flex;
            flex-direction: column;
            gap: 2px;
          }
          .cmodal-field {
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 10px 0;
            border-bottom: 1px solid var(--color-border);
          }
          .cmodal-field:last-child { border-bottom: none; }
          .cmodal-field-label {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--color-text-secondary);
          }
          .cmodal-select {
            width: 100%;
            padding: 7px 10px;
            font-size: 13px;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-sm);
            background: var(--color-surface);
            color: var(--color-text);
            outline: none;
          }
          .cmodal-select:focus {
            border-color: var(--color-primary);
            box-shadow: 0 0 0 3px rgba(59,130,246,.15);
          }
          .cmodal-date {
            padding: 7px 10px;
            font-size: 13px;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-sm);
            background: var(--color-surface);
            color: var(--color-text);
            outline: none;
          }
          .cmodal-date:focus {
            border-color: var(--color-primary);
            box-shadow: 0 0 0 3px rgba(59,130,246,.15);
          }
          .cmodal-value { font-size: 14px; color: var(--color-text); }
          .cmodal-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
          }
          .cmodal-tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
          }
          .cmodal-tag-remove {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: rgba(0,0,0,.1);
            color: var(--color-text-secondary);
            transition: background 0.15s;
            margin-left: -2px;
          }
          .cmodal-tag-remove:hover { background: var(--color-danger); color: #fff; }
          .cmodal-tag-add {
            padding: 2px 8px;
            font-size: 12px;
            border: 1px dashed var(--color-border);
            border-radius: 999px;
            background: transparent;
            color: var(--color-text-secondary);
            cursor: pointer;
            outline: none;
          }
          .cmodal-tag-add:hover { border-color: var(--color-primary); color: var(--color-primary); }
          .cmodal-comment-view {
            text-align: left;
            font-size: 13px;
            line-height: 1.5;
            color: var(--color-text);
            padding: 8px;
            border-radius: var(--radius-sm);
            border: 1px solid transparent;
            width: 100%;
            transition: border-color 0.15s, background 0.15s;
          }
          .cmodal-comment-view:hover {
            border-color: var(--color-border);
            background: var(--color-bg);
          }
          .cmodal-comment-edit { display: flex; flex-direction: column; gap: 8px; }
          .cmodal-textarea {
            width: 100%;
            padding: 8px 10px;
            font-size: 13px;
            border: 1px solid var(--color-primary);
            border-radius: var(--radius-sm);
            background: var(--color-surface);
            color: var(--color-text);
            outline: none;
            resize: vertical;
            box-shadow: 0 0 0 3px rgba(59,130,246,.15);
          }
          .cmodal-comment-actions { display: flex; gap: 8px; }
          .cmodal-history {
            margin-top: 8px;
            padding-top: 16px;
            border-top: 2px solid var(--color-border);
          }
          .cmodal-history-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--color-text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 12px;
          }
          .cmodal-history-empty {
            font-size: 13px;
            color: var(--color-text-secondary);
            font-style: italic;
          }
          .cmodal-history-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            list-style: none;
          }
          .cmodal-history-item {
            display: flex;
            flex-direction: column;
            gap: 3px;
            padding: 8px 10px;
            background: var(--color-bg);
            border-radius: var(--radius-sm);
            border-left: 3px solid var(--color-border);
          }
          .cmodal-history-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
          }
          .cmodal-history-field { font-size: 12px; font-weight: 600; color: var(--color-text); }
          .cmodal-history-who { font-size: 11px; color: var(--color-text-secondary); }
          .cmodal-history-when { font-size: 11px; color: var(--color-text-secondary); margin-left: auto; }
          .cmodal-history-change {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
          }
          .cmodal-history-old {
            font-size: 12px;
            color: var(--color-danger);
            text-decoration: line-through;
          }
          .cmodal-history-new { font-size: 12px; color: var(--color-success); font-weight: 500; }
        `}</style>
      </aside>
    </div>,
    document.body
  )
}

// Inline иконка для этапа
const GitBranchIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="6" y1="3" x2="6" y2="15"/>
    <circle cx="18" cy="6" r="3"/>
    <circle cx="6" cy="18" r="3"/>
    <path d="M18 9a9 9 0 01-9 9"/>
  </svg>
)
