import { useRef, useEffect, useCallback, useState } from 'react'
import { FixedSizeList, type ListChildComponentProps } from 'react-window'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Candidate } from '@/types/candidate'

interface CandidateTableProps {
  data: Candidate[]
  loading: boolean
  selectedKeys: Set<string>
  onSelectRow: (id: string, checked: boolean) => void
  onSelectAll: (checked: boolean) => void
  onRowClick: (candidate: Candidate) => void
  /** ID кандидатов с новым сообщением, пришедшим через WS */
  highlightedIds?: Set<string>
}

const ROW_HEIGHT = 52

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })

const formatTime = (iso: string | null) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

interface RowProps extends ListChildComponentProps {
  data: {
    items: Candidate[]
    selectedKeys: Set<string>
    onSelectRow: (id: string, checked: boolean) => void
    onRowClick: (c: Candidate) => void
    highlightedIds: Set<string>
  }
}

const CandidateRow = ({ index, style, data }: RowProps) => {
  const { items, selectedKeys, onSelectRow, onRowClick, highlightedIds } = data
  const candidate = items[index]
  if (!candidate) return null

  const isSelected = selectedKeys.has(candidate.id)
  const isHighlighted = highlightedIds.has(candidate.id)

  return (
    <div
      style={style}
      className={`ctable-row ${isSelected ? 'ctable-row--selected' : ''} ${isHighlighted ? 'ctable-row--highlight' : ''}`}
      onClick={() => onRowClick(candidate)}
      role="row"
      aria-selected={isSelected}
    >
      <div
        className="ctable-cell ctable-cell--check"
        onClick={e => e.stopPropagation()}
        role="gridcell"
      >
        <input
          type="checkbox"
          checked={isSelected}
          onChange={e => onSelectRow(candidate.id, e.target.checked)}
          aria-label="Выбрать строку"
        />
      </div>

      <div className="ctable-cell ctable-cell--name" role="gridcell">
        <div className="ctable-name">{candidate.name ?? '—'}</div>
        {candidate.phone && <div className="ctable-phone">{candidate.phone}</div>}
      </div>

      <div className="ctable-cell ctable-cell--vacancy" role="gridcell">
        <span className="ctable-text-secondary">{candidate.vacancy ?? '—'}</span>
      </div>

      <div className="ctable-cell ctable-cell--stage" role="gridcell">
        {candidate.stage ? (
          <Badge color={candidate.stage.color ?? undefined}>{candidate.stage.name}</Badge>
        ) : (
          <span className="ctable-text-secondary">—</span>
        )}
      </div>

      <div className="ctable-cell ctable-cell--responsible" role="gridcell">
        <span className="ctable-text-secondary">{candidate.responsible?.full_name ?? '—'}</span>
      </div>

      <div className="ctable-cell ctable-cell--tags" role="gridcell">
        <div className="ctable-tags">
          {candidate.tags.slice(0, 2).map(tag => (
            <Badge key={tag.id} color={tag.color ?? undefined}>{tag.name}</Badge>
          ))}
          {candidate.tags.length > 2 && (
            <span className="ctable-tags-more">+{candidate.tags.length - 2}</span>
          )}
        </div>
      </div>

      <div className="ctable-cell ctable-cell--message" role="gridcell">
        <div className="ctable-message-row">
          <span className="ctable-last-msg">{candidate.last_message ?? '—'}</span>
          {candidate.unread_count > 0 && (
            <span className="ctable-unread-badge">{candidate.unread_count}</span>
          )}
        </div>
        {candidate.last_message_at && (
          <span className="ctable-msg-time">{formatTime(candidate.last_message_at)}</span>
        )}
      </div>

      <div className="ctable-cell ctable-cell--date" role="gridcell">
        <span className="ctable-text-secondary">{formatDate(candidate.created_at)}</span>
      </div>
    </div>
  )
}

export const CandidateTable = ({
  data,
  loading,
  selectedKeys,
  onSelectRow,
  onSelectAll,
  onRowClick,
  highlightedIds = new Set(),
}: CandidateTableProps) => {
  const allSelected = data.length > 0 && selectedKeys.size === data.length
  const someSelected = selectedKeys.size > 0 && !allSelected
  const checkRef = useRef<HTMLInputElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [listHeight, setListHeight] = useState(400)

  useEffect(() => {
    if (checkRef.current) {
      checkRef.current.indeterminate = someSelected
    }
  }, [someSelected])

  useEffect(() => {
    const el = bodyRef.current
    if (!el) return
    const observer = new ResizeObserver(entries => {
      const h = entries[0]?.contentRect.height
      if (h && h > 0) setListHeight(h)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const itemData = {
    items: data,
    selectedKeys,
    onSelectRow,
    onRowClick,
    highlightedIds,
  }

  const Row = useCallback(
    (props: ListChildComponentProps) => <CandidateRow {...props} data={itemData} />,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, selectedKeys, highlightedIds]
  )

  return (
    <div className="ctable-wrap" role="grid" aria-label="Список кандидатов">
      {/* Заголовок */}
      <div className="ctable-head" role="row">
        <div className="ctable-hcell ctable-cell--check" role="columnheader">
          <input
            ref={checkRef}
            type="checkbox"
            checked={allSelected}
            onChange={e => onSelectAll(e.target.checked)}
            aria-label="Выбрать всех"
          />
        </div>
        <div className="ctable-hcell ctable-cell--name" role="columnheader">Имя / Телефон</div>
        <div className="ctable-hcell ctable-cell--vacancy" role="columnheader">Вакансия</div>
        <div className="ctable-hcell ctable-cell--stage" role="columnheader">Этап</div>
        <div className="ctable-hcell ctable-cell--responsible" role="columnheader">Ответственный</div>
        <div className="ctable-hcell ctable-cell--tags" role="columnheader">Теги</div>
        <div className="ctable-hcell ctable-cell--message" role="columnheader">Последнее сообщение</div>
        <div className="ctable-hcell ctable-cell--date" role="columnheader">Добавлен</div>
      </div>

      {/* Тело */}
      <div className="ctable-body" ref={bodyRef}>
        {loading ? (
          <div className="ctable-loading"><Spinner size="lg" /></div>
        ) : data.length === 0 ? (
          <EmptyState title="Кандидаты не найдены" description="Попробуйте изменить фильтры" />
        ) : (
          <FixedSizeList
            height={listHeight}
            width="100%"
            itemCount={data.length}
            itemSize={ROW_HEIGHT}
          >
            {Row}
          </FixedSizeList>
        )}
      </div>

      <style>{`
        .ctable-wrap {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .ctable-head {
          display: flex;
          align-items: center;
          background: var(--color-bg);
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .ctable-hcell {
          padding: 10px 12px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
          white-space: nowrap;
          flex-shrink: 0;
        }
        .ctable-body { flex: 1; overflow: hidden; }
        .ctable-row {
          display: flex;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          cursor: pointer;
          transition: background 0.1s;
        }
        .ctable-row:hover { background: #f8fafc; }
        .ctable-row--selected { background: #eff6ff; }
        .ctable-row--selected:hover { background: #dbeafe; }
        .ctable-row--highlight {
          animation: rowPulse 1.5s ease;
        }
        @keyframes rowPulse {
          0% { background: #fef3c7; }
          100% { background: transparent; }
        }
        .ctable-cell {
          padding: 0 12px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .ctable-cell--check { width: 44px; display: flex; align-items: center; justify-content: center; }
        .ctable-cell--name { flex: 1; min-width: 160px; display: flex; flex-direction: column; gap: 2px; white-space: normal; }
        .ctable-cell--vacancy { width: 150px; }
        .ctable-cell--stage { width: 130px; }
        .ctable-cell--responsible { width: 140px; }
        .ctable-cell--tags { width: 160px; }
        .ctable-cell--message { flex: 1; min-width: 180px; display: flex; flex-direction: column; gap: 2px; white-space: normal; }
        .ctable-cell--date { width: 90px; }
        .ctable-name { font-size: 14px; font-weight: 500; color: var(--color-text); line-height: 1.3; }
        .ctable-phone { font-size: 12px; color: var(--color-text-secondary); }
        .ctable-text-secondary { font-size: 13px; color: var(--color-text-secondary); }
        .ctable-tags { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
        .ctable-tags-more { font-size: 11px; color: var(--color-text-secondary); }
        .ctable-message-row {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .ctable-last-msg {
          font-size: 13px;
          color: var(--color-text-secondary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 200px;
        }
        .ctable-unread-badge {
          background: var(--color-danger);
          color: #fff;
          font-size: 11px;
          font-weight: 600;
          min-width: 18px;
          height: 18px;
          border-radius: 999px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 5px;
          flex-shrink: 0;
        }
        .ctable-msg-time { font-size: 11px; color: var(--color-text-secondary); }
        .ctable-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 200px;
        }
      `}</style>
    </div>
  )
}
