import { type ReactNode } from 'react'
import clsx from 'clsx'
import { Spinner } from './Spinner'
import { EmptyState } from './EmptyState'

export interface Column<T> {
  key: string
  title: string
  width?: string | number
  align?: 'left' | 'center' | 'right'
  render: (row: T, index: number) => ReactNode
}

interface TableProps<T> {
  columns: Column<T>[]
  data: T[]
  rowKey: (row: T) => string
  loading?: boolean
  emptyText?: string
  onRowClick?: (row: T) => void
  selectedKeys?: Set<string>
  onSelectRow?: (key: string, checked: boolean) => void
  onSelectAll?: (checked: boolean) => void
}

export function Table<T>({
  columns,
  data,
  rowKey,
  loading,
  emptyText,
  onRowClick,
  selectedKeys,
  onSelectRow,
  onSelectAll,
}: TableProps<T>) {
  const hasSelection = !!onSelectRow

  return (
    <div className="table-wrap">
      {loading && (
        <div className="table-loading">
          <Spinner size="md" />
        </div>
      )}
      <table className="table">
        <thead>
          <tr>
            {hasSelection && (
              <th className="table-th table-th--check">
                <input
                  type="checkbox"
                  checked={data.length > 0 && selectedKeys?.size === data.length}
                  onChange={e => onSelectAll?.(e.target.checked)}
                  aria-label="Выбрать все"
                />
              </th>
            )}
            {columns.map(col => (
              <th
                key={col.key}
                className="table-th"
                style={{ width: col.width, textAlign: col.align ?? 'left' }}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {!loading && data.length === 0 ? (
            <tr>
              <td colSpan={columns.length + (hasSelection ? 1 : 0)}>
                <EmptyState title={emptyText} />
              </td>
            </tr>
          ) : (
            data.map((row, i) => {
              const key = rowKey(row)
              const isSelected = selectedKeys?.has(key) ?? false
              return (
                <tr
                  key={key}
                  className={clsx(
                    'table-row',
                    onRowClick && 'table-row--clickable',
                    isSelected && 'table-row--selected'
                  )}
                  onClick={() => onRowClick?.(row)}
                >
                  {hasSelection && (
                    <td className="table-td table-td--check" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={e => onSelectRow(key, e.target.checked)}
                        aria-label="Выбрать строку"
                      />
                    </td>
                  )}
                  {columns.map(col => (
                    <td
                      key={col.key}
                      className="table-td"
                      style={{ textAlign: col.align ?? 'left' }}
                    >
                      {col.render(row, i)}
                    </td>
                  ))}
                </tr>
              )
            })
          )}
        </tbody>
      </table>

      <style>{`
        .table-wrap { position: relative; overflow-x: auto; }
        .table-loading {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(255,255,255,.6);
          z-index: 1;
        }
        .table {
          width: 100%;
          border-collapse: collapse;
          font-size: 14px;
        }
        .table-th {
          padding: 10px 14px;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
          border-bottom: 1px solid var(--color-border);
          background: var(--color-bg);
          white-space: nowrap;
        }
        .table-th--check, .table-td--check { width: 40px; text-align: center; }
        .table-td {
          padding: 11px 14px;
          border-bottom: 1px solid var(--color-border);
          color: var(--color-text);
          vertical-align: middle;
        }
        .table-row--clickable { cursor: pointer; }
        .table-row--clickable:hover .table-td { background: #f8fafc; }
        .table-row--selected .table-td { background: #eff6ff; }
      `}</style>
    </div>
  )
}
