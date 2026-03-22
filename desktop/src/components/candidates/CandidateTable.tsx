import { useRef, useEffect, useCallback, useState } from 'react'
import { FixedSizeList, type ListChildComponentProps } from 'react-window'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Settings2, Copy, Check } from 'lucide-react'
import type { Candidate } from '@/types/candidate'

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------
export type ColumnKey = 'name' | 'vacancy' | 'stage' | 'responsible' | 'location' | 'tags' | 'message' | 'date'

interface ColDef {
  key: ColumnKey
  label: string
  required?: boolean
  defaultVisible: boolean
}

const COLUMN_DEFS: ColDef[] = [
  { key: 'name',        label: 'Имя / Телефон',       required: true,  defaultVisible: true  },
  { key: 'vacancy',     label: 'Вакансия',             defaultVisible: true  },
  { key: 'stage',       label: 'Этап',                 defaultVisible: true  },
  { key: 'responsible', label: 'Ответственный',        defaultVisible: true  },
  { key: 'location',    label: 'Локация',              defaultVisible: false },
  { key: 'tags',        label: 'Теги',                 defaultVisible: true  },
  { key: 'message',     label: 'Последнее сообщение',  defaultVisible: true  },
  { key: 'date',        label: 'Добавлен',             defaultVisible: true  },
]

const STORAGE_KEY = 'ctable_visible_cols'

function loadVisibleCols(): Set<ColumnKey> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const arr = JSON.parse(raw) as ColumnKey[]
      if (Array.isArray(arr) && arr.length) return new Set(arr)
    }
  } catch { /* ignore */ }
  return new Set(COLUMN_DEFS.filter(c => c.defaultVisible).map(c => c.key))
}

function saveVisibleCols(cols: Set<ColumnKey>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...cols]))
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })

const formatTime = (iso: string | null) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString())
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

const displayName = (c: Candidate) =>
  c.name?.trim() || c.phone || `Кандидат #${c.id.slice(0, 6)}`

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------
interface RowProps extends ListChildComponentProps {
  data: {
    items: Candidate[]
    selectedKeys: Set<string>
    onSelectRow: (id: string, checked: boolean) => void
    onRowClick: (c: Candidate) => void
    highlightedIds: Set<string>
    visibleCols: Set<ColumnKey>
  }
}

const CandidateRow = ({ index, style, data }: RowProps) => {
  const { items, selectedKeys, onSelectRow, onRowClick, highlightedIds, visibleCols } = data
  const candidate = items[index]
  if (!candidate) return null

  const isSelected = selectedKeys.has(candidate.id)
  const isHighlighted = highlightedIds.has(candidate.id)
  const isNoName = !candidate.name?.trim()

  return (
    <div
      style={style}
      className={`ctable-row ${isSelected ? 'ctable-row--selected' : ''} ${isHighlighted ? 'ctable-row--highlight' : ''}`}
      onClick={() => onRowClick(candidate)}
      role="row"
      aria-selected={isSelected}
    >
      <div className="ctable-cell ctable-cell--check" onClick={e => e.stopPropagation()} role="gridcell">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={e => onSelectRow(candidate.id, e.target.checked)}
          aria-label="Выбрать строку"
        />
      </div>

      {/* name — always visible */}
      <div className="ctable-cell ctable-cell--name" role="gridcell">
        <div className={`ctable-name ${isNoName ? 'ctable-name--unknown' : ''}`}>
          {displayName(candidate)}
        </div>
        {candidate.phone && candidate.name?.trim() && (
          <div className="ctable-phone">{candidate.phone}</div>
        )}
      </div>

      {visibleCols.has('vacancy') && (
        <div className="ctable-cell ctable-cell--vacancy" role="gridcell">
          <span className="ctable-text-secondary">{candidate.vacancy ?? '—'}</span>
        </div>
      )}

      {visibleCols.has('stage') && (
        <div className="ctable-cell ctable-cell--stage" role="gridcell">
          {candidate.stage
            ? <Badge color={candidate.stage.color ?? undefined}>{candidate.stage.name}</Badge>
            : <span className="ctable-text-secondary">—</span>}
        </div>
      )}

      {visibleCols.has('responsible') && (
        <div className="ctable-cell ctable-cell--responsible" role="gridcell">
          <span className="ctable-text-secondary">{candidate.responsible?.full_name ?? '—'}</span>
        </div>
      )}

      {visibleCols.has('location') && (
        <div className="ctable-cell ctable-cell--location" role="gridcell">
          <span className="ctable-text-secondary">{candidate.location ?? '—'}</span>
        </div>
      )}

      {visibleCols.has('tags') && (
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
      )}

      {visibleCols.has('message') && (
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
      )}

      {visibleCols.has('date') && (
        <div className="ctable-cell ctable-cell--date" role="gridcell">
          <span className="ctable-text-secondary">{formatDate(candidate.created_at)}</span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Column settings popover
// ---------------------------------------------------------------------------
const ColSettings = ({
  visibleCols,
  onChange,
}: {
  visibleCols: Set<ColumnKey>
  onChange: (cols: Set<ColumnKey>) => void
}) => {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = (key: ColumnKey) => {
    const next = new Set(visibleCols)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    onChange(next)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        className="ctable-icon-btn"
        title="Настройка столбцов"
        onClick={() => setOpen(v => !v)}
        aria-label="Настройка столбцов"
      >
        <Settings2 size={15} />
      </button>

      {open && (
        <div className="ctable-col-popover">
          <div className="ctable-col-popover-title">Столбцы</div>
          {COLUMN_DEFS.map(col => (
            <label key={col.key} className="ctable-col-item">
              <input
                type="checkbox"
                checked={visibleCols.has(col.key)}
                disabled={col.required}
                onChange={() => !col.required && toggle(col.key)}
              />
              <span>{col.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Copy to clipboard
// ---------------------------------------------------------------------------
function buildClipboardText(candidates: Candidate[], visibleCols: Set<ColumnKey>): string {
  const colOrder: ColumnKey[] = ['name', 'vacancy', 'stage', 'responsible', 'location', 'tags', 'message', 'date']
  const activeCols = colOrder.filter(k => visibleCols.has(k))

  const headers = activeCols.map(k => COLUMN_DEFS.find(c => c.key === k)!.label)

  const rows = candidates.map(c => activeCols.map(k => {
    switch (k) {
      case 'name':        return `${displayName(c)}${c.phone && c.name?.trim() ? ' / ' + c.phone : ''}`
      case 'vacancy':     return c.vacancy ?? ''
      case 'stage':       return c.stage?.name ?? ''
      case 'responsible': return c.responsible?.full_name ?? ''
      case 'location':    return c.location ?? ''
      case 'tags':        return c.tags.map(t => t.name).join(', ')
      case 'message':     return c.last_message ?? ''
      case 'date':        return formatDate(c.created_at)
      default:            return ''
    }
  }))

  return [headers, ...rows].map(r => r.join('\t')).join('\n')
}

const CopyButton = ({
  selectedKeys,
  data,
  visibleCols,
}: {
  selectedKeys: Set<string>
  data: Candidate[]
  visibleCols: Set<ColumnKey>
}) => {
  const [copied, setCopied] = useState(false)

  if (selectedKeys.size === 0) return null

  const handleCopy = async () => {
    const selected = data.filter(c => selectedKeys.has(c.id))
    const text = buildClipboardText(selected, visibleCols)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      className={`ctable-icon-btn ctable-copy-btn ${copied ? 'ctable-copy-btn--done' : ''}`}
      title={copied ? 'Скопировано!' : `Копировать ${selectedKeys.size} кандидата(ов)`}
      onClick={handleCopy}
      aria-label="Копировать выбранных"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
      <span>{copied ? 'Скопировано' : `Копировать (${selectedKeys.size})`}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
interface CandidateTableProps {
  data: Candidate[]
  loading: boolean
  selectedKeys: Set<string>
  onSelectRow: (id: string, checked: boolean) => void
  onSelectAll: (checked: boolean) => void
  onRowClick: (candidate: Candidate) => void
  highlightedIds?: Set<string>
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
  const [visibleCols, setVisibleCols] = useState<Set<ColumnKey>>(loadVisibleCols)

  useEffect(() => {
    if (checkRef.current) checkRef.current.indeterminate = someSelected
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

  const handleColChange = (cols: Set<ColumnKey>) => {
    setVisibleCols(cols)
    saveVisibleCols(cols)
  }

  const itemData = {
    items: data,
    selectedKeys,
    onSelectRow,
    onRowClick,
    highlightedIds,
    visibleCols,
  }

  const Row = useCallback(
    (props: ListChildComponentProps) => <CandidateRow {...props} data={itemData} />,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, selectedKeys, highlightedIds, visibleCols]
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

        <div className="ctable-hcell ctable-cell--name" role="columnheader" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>Имя / Телефон</span>
          <div className="ctable-head-actions" onClick={e => e.stopPropagation()}>
            <CopyButton selectedKeys={selectedKeys} data={data} visibleCols={visibleCols} />
            <ColSettings visibleCols={visibleCols} onChange={handleColChange} />
          </div>
        </div>

        {visibleCols.has('vacancy')     && <div className="ctable-hcell ctable-cell--vacancy"     role="columnheader">Вакансия</div>}
        {visibleCols.has('stage')       && <div className="ctable-hcell ctable-cell--stage"       role="columnheader">Этап</div>}
        {visibleCols.has('responsible') && <div className="ctable-hcell ctable-cell--responsible" role="columnheader">Ответственный</div>}
        {visibleCols.has('location')    && <div className="ctable-hcell ctable-cell--location"    role="columnheader">Локация</div>}
        {visibleCols.has('tags')        && <div className="ctable-hcell ctable-cell--tags"        role="columnheader">Теги</div>}
        {visibleCols.has('message')     && <div className="ctable-hcell ctable-cell--message"     role="columnheader">Последнее сообщение</div>}
        {visibleCols.has('date')        && <div className="ctable-hcell ctable-cell--date"        role="columnheader">Добавлен</div>}
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
        .ctable-wrap { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
        .ctable-head {
          display: flex; align-items: center;
          background: var(--color-bg);
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .ctable-hcell {
          padding: 10px 12px;
          font-size: 11px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.05em;
          color: var(--color-text-secondary);
          white-space: nowrap; flex-shrink: 0;
        }
        .ctable-cell--name .ctable-hcell,
        .ctable-hcell.ctable-cell--name {
          display: flex; align-items: center; gap: 8px;
        }
        .ctable-head-actions { display: flex; align-items: center; gap: 4px; margin-left: auto; }
        .ctable-body { flex: 1; overflow: hidden; }
        .ctable-row {
          display: flex; align-items: center;
          border-bottom: 1px solid var(--color-border);
          cursor: pointer; transition: background 0.1s;
        }
        .ctable-row:hover { background: #f8fafc; }
        .ctable-row--selected { background: #eff6ff; }
        .ctable-row--selected:hover { background: #dbeafe; }
        .ctable-row--highlight { animation: rowPulse 1.5s ease; }
        @keyframes rowPulse { 0% { background: #fef3c7; } 100% { background: transparent; } }
        .ctable-cell {
          padding: 0 12px; overflow: hidden;
          text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0;
        }
        .ctable-cell--check    { width: 44px; display: flex; align-items: center; justify-content: center; }
        .ctable-cell--name     { flex: 1; min-width: 160px; display: flex; flex-direction: column; gap: 2px; white-space: normal; }
        .ctable-hcell.ctable-cell--name { flex-direction: row; align-items: center; }
        .ctable-cell--vacancy     { width: 150px; }
        .ctable-cell--stage       { width: 130px; }
        .ctable-cell--responsible { width: 140px; }
        .ctable-cell--location    { width: 120px; }
        .ctable-cell--tags        { width: 160px; }
        .ctable-cell--message     { flex: 1; min-width: 180px; display: flex; flex-direction: column; gap: 2px; white-space: normal; }
        .ctable-cell--date        { width: 90px; }
        .ctable-name { font-size: 14px; font-weight: 500; color: var(--color-text); line-height: 1.3; }
        .ctable-name--unknown { font-style: italic; color: var(--color-text-secondary); }
        .ctable-phone { font-size: 12px; color: var(--color-text-secondary); }
        .ctable-text-secondary { font-size: 13px; color: var(--color-text-secondary); }
        .ctable-tags { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
        .ctable-tags-more { font-size: 11px; color: var(--color-text-secondary); }
        .ctable-message-row { display: flex; align-items: center; gap: 6px; }
        .ctable-last-msg {
          font-size: 13px; color: var(--color-text-secondary);
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px;
        }
        .ctable-unread-badge {
          background: var(--color-danger); color: #fff;
          font-size: 11px; font-weight: 600;
          min-width: 18px; height: 18px; border-radius: 999px;
          display: inline-flex; align-items: center; justify-content: center;
          padding: 0 5px; flex-shrink: 0;
        }
        .ctable-msg-time { font-size: 11px; color: var(--color-text-secondary); }
        .ctable-loading { display: flex; align-items: center; justify-content: center; height: 200px; }

        /* Icon button */
        .ctable-icon-btn {
          background: none; border: 1px solid transparent; border-radius: var(--radius-sm);
          cursor: pointer; color: var(--color-text-secondary);
          display: inline-flex; align-items: center; gap: 5px;
          padding: 3px 6px; font-size: 11px; font-weight: 500;
          transition: background 0.1s, color 0.1s, border-color 0.1s;
        }
        .ctable-icon-btn:hover {
          background: var(--color-surface); color: var(--color-text);
          border-color: var(--color-border);
        }
        .ctable-copy-btn { color: var(--color-text-secondary); }
        .ctable-copy-btn--done { color: #16a34a !important; border-color: #16a34a !important; }

        /* Column popover */
        .ctable-col-popover {
          position: absolute; top: calc(100% + 6px); right: 0; z-index: 200;
          background: var(--color-surface); border: 1px solid var(--color-border);
          border-radius: var(--radius-sm); box-shadow: 0 4px 16px rgba(0,0,0,0.12);
          padding: 8px; min-width: 190px;
        }
        .ctable-col-popover-title {
          font-size: 11px; font-weight: 600; text-transform: uppercase;
          letter-spacing: 0.05em; color: var(--color-text-secondary);
          padding: 2px 4px 8px; border-bottom: 1px solid var(--color-border); margin-bottom: 6px;
        }
        .ctable-col-item {
          display: flex; align-items: center; gap: 8px;
          padding: 5px 4px; cursor: pointer; border-radius: 4px;
          font-size: 13px; color: var(--color-text);
          transition: background 0.1s;
        }
        .ctable-col-item:hover { background: var(--color-bg); }
        .ctable-col-item input[type=checkbox]:disabled { opacity: 0.4; cursor: not-allowed; }
      `}</style>
    </div>
  )
}
