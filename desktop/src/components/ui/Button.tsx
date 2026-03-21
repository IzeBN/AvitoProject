import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import clsx from 'clsx'
import { Spinner } from './Spinner'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: ReactNode
  children?: ReactNode
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  danger: 'btn-danger',
  ghost: 'btn-ghost',
}

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'btn-sm',
  md: 'btn-md',
  lg: 'btn-lg',
}

export const Button = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  disabled,
  className,
  ...props
}: ButtonProps) => {
  return (
    <button
      className={clsx('btn', variantStyles[variant], sizeStyles[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Spinner size="sm" />
      ) : (
        icon && <span className="btn-icon">{icon}</span>
      )}
      {children && <span>{children}</span>}

      <style>{`
        .btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          font-weight: 500;
          border-radius: var(--radius-sm);
          transition: background 0.15s, opacity 0.15s, box-shadow 0.15s;
          white-space: nowrap;
          outline: none;
        }
        .btn:focus-visible {
          box-shadow: 0 0 0 3px rgba(59,130,246,.35);
        }
        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .btn-sm { padding: 5px 12px; font-size: 13px; }
        .btn-md { padding: 8px 16px; font-size: 14px; }
        .btn-lg { padding: 11px 22px; font-size: 15px; }
        .btn-primary {
          background: var(--color-primary);
          color: #fff;
        }
        .btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
        .btn-secondary {
          background: var(--color-surface);
          color: var(--color-text);
          border: 1px solid var(--color-border);
        }
        .btn-secondary:hover:not(:disabled) { background: var(--color-bg); }
        .btn-danger {
          background: var(--color-danger);
          color: #fff;
        }
        .btn-danger:hover:not(:disabled) { background: #dc2626; }
        .btn-ghost {
          background: transparent;
          color: var(--color-text-secondary);
        }
        .btn-ghost:hover:not(:disabled) {
          background: var(--color-bg);
          color: var(--color-text);
        }
        .btn-icon { display: flex; align-items: center; }
      `}</style>
    </button>
  )
}
