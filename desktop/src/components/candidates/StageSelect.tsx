import { type SelectHTMLAttributes, forwardRef } from 'react'

interface StageOption {
  id: string
  name: string
  color: string | null
}

interface StageSelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  stages: StageOption[]
  placeholder?: string
}

export const StageSelect = forwardRef<HTMLSelectElement, StageSelectProps>(
  ({ stages, placeholder = 'Все этапы', className, ...props }, ref) => {
    const selected = stages.find(s => s.id === String(props.value ?? ''))

    return (
      <div className="stage-select-wrap">
        {selected?.color && (
          <span
            className="stage-select-dot"
            style={{ background: selected.color }}
          />
        )}
        <select
          ref={ref}
          className={`stage-select ${className ?? ''}`}
          style={
            selected?.color
              ? { paddingLeft: '28px', borderColor: selected.color + '88' }
              : undefined
          }
          {...props}
        >
          <option value="">{placeholder}</option>
          {stages.map(s => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <style>{`
          .stage-select-wrap {
            position: relative;
            display: inline-flex;
            align-items: center;
            width: 100%;
          }
          .stage-select-dot {
            position: absolute;
            left: 10px;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            z-index: 1;
            pointer-events: none;
            flex-shrink: 0;
          }
          .stage-select {
            width: 100%;
            padding: 8px 12px;
            font-size: 14px;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-sm);
            background: var(--color-surface);
            color: var(--color-text);
            outline: none;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 10px center;
            padding-right: 30px;
            transition: border-color 0.15s, box-shadow 0.15s;
          }
          .stage-select:focus {
            border-color: var(--color-primary);
            box-shadow: 0 0 0 3px rgba(59,130,246,.15);
          }
        `}</style>
      </div>
    )
  }
)

StageSelect.displayName = 'StageSelect'
