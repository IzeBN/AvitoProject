import {
  type InputHTMLAttributes,
  type ReactNode,
  forwardRef,
} from 'react'
import clsx from 'clsx'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, leftIcon, rightIcon, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')

    return (
      <div className="input-wrap">
        {label && (
          <label htmlFor={inputId} className="input-label">
            {label}
          </label>
        )}
        <div className={clsx('input-row', error && 'input-row--error')}>
          {leftIcon && <span className="input-icon input-icon--left">{leftIcon}</span>}
          <input
            ref={ref}
            id={inputId}
            className={clsx('input-field', leftIcon && 'has-left', rightIcon && 'has-right', className)}
            aria-invalid={!!error}
            aria-describedby={error ? `${inputId}-error` : undefined}
            {...props}
          />
          {rightIcon && <span className="input-icon input-icon--right">{rightIcon}</span>}
        </div>
        {error && (
          <p id={`${inputId}-error`} className="input-error" role="alert">
            {error}
          </p>
        )}
        {hint && !error && <p className="input-hint">{hint}</p>}

        <style>{`
          .input-wrap { display: flex; flex-direction: column; gap: 4px; }
          .input-label { font-size: 13px; font-weight: 500; color: var(--color-text); }
          .input-row { position: relative; display: flex; align-items: center; }
          .input-field {
            width: 100%;
            padding: 8px 12px;
            font-size: 14px;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-sm);
            background: var(--color-surface);
            color: var(--color-text);
            outline: none;
            transition: border-color 0.15s, box-shadow 0.15s;
          }
          .input-field:focus {
            border-color: var(--color-primary);
            box-shadow: 0 0 0 3px rgba(59,130,246,.15);
          }
          .input-field::placeholder { color: var(--color-text-secondary); }
          .input-field.has-left { padding-left: 36px; }
          .input-field.has-right { padding-right: 36px; }
          .input-row--error .input-field {
            border-color: var(--color-danger);
          }
          .input-row--error .input-field:focus {
            box-shadow: 0 0 0 3px rgba(239,68,68,.15);
          }
          .input-icon {
            position: absolute;
            display: flex;
            align-items: center;
            color: var(--color-text-secondary);
            pointer-events: none;
          }
          .input-icon--left { left: 10px; }
          .input-icon--right { right: 10px; }
          .input-error { font-size: 12px; color: var(--color-danger); }
          .input-hint { font-size: 12px; color: var(--color-text-secondary); }
        `}</style>
      </div>
    )
  }
)

Input.displayName = 'Input'
