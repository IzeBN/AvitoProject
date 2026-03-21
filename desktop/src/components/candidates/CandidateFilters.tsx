import { type ChangeEvent } from 'react'
import { X } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { StageSelect } from './StageSelect'
import type { CandidateFilters as Filters } from '@/types/candidate'

interface FilterOption {
  id: string
  name: string
  color?: string | null
}

interface CandidateFiltersProps {
  filters: Filters
  search: string
  onSearchChange: (v: string) => void
  onChange: (filters: Filters) => void
  onReset: () => void
  stages: FilterOption[]
  responsibles: FilterOption[]
  departments: FilterOption[]
  accounts: FilterOption[]
  tags: FilterOption[]
}

export const CandidateFilters = ({
  filters,
  search,
  onSearchChange,
  onChange,
  onReset,
  stages,
  responsibles,
  departments,
  accounts,
  tags,
}: CandidateFiltersProps) => {
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    onChange({ ...filters, [key]: value })
  }

  const handleSelect = (key: keyof Filters) => (e: ChangeEvent<HTMLSelectElement>) => {
    set(key, e.target.value || undefined)
  }

  const toggleTag = (tagId: string) => {
    const current = filters.tag_ids ?? []
    const next = current.includes(tagId)
      ? current.filter(id => id !== tagId)
      : [...current, tagId]
    set('tag_ids', next.length ? next : undefined)
  }

  const hasActiveFilters =
    !!filters.stage_id ||
    !!filters.responsible_id ||
    !!filters.department_id ||
    !!filters.avito_account_id ||
    (filters.tag_ids?.length ?? 0) > 0 ||
    !!filters.has_new_message ||
    !!filters.created_at_from ||
    !!filters.created_at_to ||
    !!filters.due_date_from ||
    !!filters.due_date_to ||
    !!search

  return (
    <aside className="cfilters">
      <div className="cfilters-section">
        <Input
          placeholder="Поиск по имени, телефону..."
          value={search}
          onChange={e => onSearchChange(e.target.value)}
        />
      </div>

      <div className="cfilters-section">
        <label className="cfilters-label">Этап</label>
        <StageSelect
          stages={stages.map(s => ({ id: s.id, name: s.name, color: s.color ?? null }))}
          value={filters.stage_id ?? ''}
          onChange={handleSelect('stage_id')}
          placeholder="Все этапы"
        />
      </div>

      <div className="cfilters-section">
        <label className="cfilters-label">Ответственный</label>
        <select
          className="cfilters-select"
          value={filters.responsible_id ?? ''}
          onChange={handleSelect('responsible_id')}
        >
          <option value="">Все</option>
          {responsibles.map(r => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
      </div>

      <div className="cfilters-section">
        <label className="cfilters-label">Отдел</label>
        <select
          className="cfilters-select"
          value={filters.department_id ?? ''}
          onChange={handleSelect('department_id')}
        >
          <option value="">Все</option>
          {departments.map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
      </div>

      <div className="cfilters-section">
        <label className="cfilters-label">Аккаунт</label>
        <select
          className="cfilters-select"
          value={filters.avito_account_id ?? ''}
          onChange={handleSelect('avito_account_id')}
        >
          <option value="">Все</option>
          {accounts.map(a => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      {tags.length > 0 && (
        <div className="cfilters-section">
          <label className="cfilters-label">Теги</label>
          <div className="cfilters-tags">
            {tags.map(tag => {
              const active = filters.tag_ids?.includes(tag.id)
              return (
                <button
                  key={tag.id}
                  className={`cfilters-tag ${active ? 'cfilters-tag--active' : ''}`}
                  style={
                    active && tag.color
                      ? { background: tag.color + '22', borderColor: tag.color, color: tag.color }
                      : undefined
                  }
                  onClick={() => toggleTag(tag.id)}
                  type="button"
                >
                  {tag.name}
                </button>
              )
            })}
          </div>
        </div>
      )}

      <div className="cfilters-section">
        <label className="cfilters-check-row">
          <input
            type="checkbox"
            checked={filters.has_new_message === true}
            onChange={e => set('has_new_message', e.target.checked || undefined)}
          />
          <span>Только новые сообщения</span>
        </label>
      </div>

      <div className="cfilters-section">
        <label className="cfilters-label">Дата создания</label>
        <div className="cfilters-range">
          <input
            type="date"
            className="cfilters-date"
            value={filters.created_at_from ?? ''}
            onChange={e => set('created_at_from', e.target.value || undefined)}
          />
          <span className="cfilters-range-sep">—</span>
          <input
            type="date"
            className="cfilters-date"
            value={filters.created_at_to ?? ''}
            onChange={e => set('created_at_to', e.target.value || undefined)}
          />
        </div>
      </div>

      <div className="cfilters-section">
        <label className="cfilters-label">Дедлайн</label>
        <div className="cfilters-range">
          <input
            type="date"
            className="cfilters-date"
            value={filters.due_date_from ?? ''}
            onChange={e => set('due_date_from', e.target.value || undefined)}
          />
          <span className="cfilters-range-sep">—</span>
          <input
            type="date"
            className="cfilters-date"
            value={filters.due_date_to ?? ''}
            onChange={e => set('due_date_to', e.target.value || undefined)}
          />
        </div>
      </div>

      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          icon={<X size={14} />}
          onClick={onReset}
          style={{ marginTop: 4 }}
        >
          Сбросить фильтры
        </Button>
      )}

      <style>{`
        .cfilters {
          display: flex;
          flex-direction: column;
          gap: 4px;
          padding: 16px;
          border-right: 1px solid var(--color-border);
          overflow-y: auto;
          width: 240px;
          flex-shrink: 0;
        }
        .cfilters-section {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 8px 0;
          border-bottom: 1px solid var(--color-border);
        }
        .cfilters-section:last-child { border-bottom: none; }
        .cfilters-label {
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-secondary);
        }
        .cfilters-select {
          width: 100%;
          padding: 7px 10px;
          font-size: 13px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
          cursor: pointer;
        }
        .cfilters-select:focus {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 3px rgba(59,130,246,.15);
        }
        .cfilters-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .cfilters-tag {
          padding: 3px 10px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 500;
          border: 1px solid var(--color-border);
          background: var(--color-bg);
          color: var(--color-text-secondary);
          cursor: pointer;
          transition: all 0.15s;
        }
        .cfilters-tag--active {
          background: #eff6ff;
          border-color: var(--color-primary);
          color: var(--color-primary);
        }
        .cfilters-check-row {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          color: var(--color-text);
          cursor: pointer;
        }
        .cfilters-range {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .cfilters-date {
          flex: 1;
          padding: 6px 8px;
          font-size: 12px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
          min-width: 0;
        }
        .cfilters-date:focus {
          border-color: var(--color-primary);
        }
        .cfilters-range-sep {
          font-size: 12px;
          color: var(--color-text-secondary);
          flex-shrink: 0;
        }
      `}</style>
    </aside>
  )
}
