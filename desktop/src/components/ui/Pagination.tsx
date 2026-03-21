import { ChevronLeft, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

function getPages(current: number, total: number): Array<number | '...'> {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: Array<number | '...'> = [1]
  if (current > 3) pages.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
}

export const Pagination = ({ page, totalPages, onPageChange }: PaginationProps) => {
  if (totalPages <= 1) return null

  const pages = getPages(page, totalPages)

  return (
    <nav className="pagination" aria-label="Навигация по страницам">
      <button
        className="pg-btn"
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        aria-label="Предыдущая страница"
      >
        <ChevronLeft size={16} />
      </button>

      {pages.map((p, i) =>
        p === '...' ? (
          <span key={`dots-${i}`} className="pg-dots">…</span>
        ) : (
          <button
            key={p}
            className={clsx('pg-btn', p === page && 'pg-btn--active')}
            onClick={() => onPageChange(p)}
            aria-current={p === page ? 'page' : undefined}
          >
            {p}
          </button>
        )
      )}

      <button
        className="pg-btn"
        onClick={() => onPageChange(page + 1)}
        disabled={page === totalPages}
        aria-label="Следующая страница"
      >
        <ChevronRight size={16} />
      </button>

      <style>{`
        .pagination {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .pg-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 32px;
          height: 32px;
          padding: 0 6px;
          border-radius: var(--radius-sm);
          font-size: 13px;
          font-weight: 500;
          color: var(--color-text-secondary);
          transition: background 0.15s, color 0.15s;
        }
        .pg-btn:hover:not(:disabled) {
          background: var(--color-bg);
          color: var(--color-text);
        }
        .pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .pg-btn--active {
          background: var(--color-primary);
          color: #fff;
        }
        .pg-btn--active:hover { background: var(--color-primary-hover); color: #fff; }
        .pg-dots {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 32px;
          font-size: 13px;
          color: var(--color-text-secondary);
        }
      `}</style>
    </nav>
  )
}
