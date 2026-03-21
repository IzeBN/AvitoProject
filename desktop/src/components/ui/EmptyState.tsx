import { type ReactNode } from 'react'
import { Inbox } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
}

export const EmptyState = ({
  title = 'Ничего не найдено',
  description,
  icon,
  action,
}: EmptyStateProps) => {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        {icon ?? <Inbox size={40} strokeWidth={1.5} />}
      </div>
      <p className="empty-title">{title}</p>
      {description && <p className="empty-desc">{description}</p>}
      {action && <div className="empty-action">{action}</div>}

      <style>{`
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 48px 24px;
          text-align: center;
        }
        .empty-icon { color: var(--color-text-secondary); opacity: 0.5; }
        .empty-title { font-size: 15px; font-weight: 500; color: var(--color-text-secondary); }
        .empty-desc { font-size: 13px; color: var(--color-text-secondary); opacity: 0.7; max-width: 320px; }
        .empty-action { margin-top: 8px; }
      `}</style>
    </div>
  )
}
