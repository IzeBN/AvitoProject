import { type ReactNode } from 'react'
import clsx from 'clsx'

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'custom'

interface BadgeProps {
  variant?: BadgeVariant
  /** Произвольный цвет фона (HEX/rgb). Включает variant="custom" */
  color?: string
  children: ReactNode
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'badge-default',
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-info',
  custom: '',
}

export const Badge = ({ variant = 'default', color, children, className }: BadgeProps) => {
  const isCustom = !!color
  return (
    <span
      className={clsx('badge', !isCustom && variantStyles[variant], className)}
      style={
        isCustom
          ? { backgroundColor: color + '22', color, border: `1px solid ${color}55` }
          : undefined
      }
    >
      {children}
      <style>{`
        .badge {
          display: inline-flex;
          align-items: center;
          padding: 2px 8px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 500;
          border: 1px solid transparent;
          white-space: nowrap;
        }
        .badge-default {
          background: var(--color-bg);
          color: var(--color-text-secondary);
          border-color: var(--color-border);
        }
        .badge-success {
          background: #dcfce7;
          color: #15803d;
          border-color: #bbf7d0;
        }
        .badge-warning {
          background: #fef3c7;
          color: #b45309;
          border-color: #fde68a;
        }
        .badge-danger {
          background: #fee2e2;
          color: #b91c1c;
          border-color: #fecaca;
        }
        .badge-info {
          background: #dbeafe;
          color: #1d4ed8;
          border-color: #bfdbfe;
        }
      `}</style>
    </span>
  )
}
