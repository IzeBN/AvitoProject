import {
  type ReactNode,
  useEffect,
  useCallback,
} from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import clsx from 'clsx'

type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  footer?: ReactNode
  size?: ModalSize
  /** Закрывать при клике на backdrop */
  closeOnBackdrop?: boolean
}

const sizeWidths: Record<ModalSize, string> = {
  sm: '400px',
  md: '560px',
  lg: '720px',
  xl: '900px',
}

export const Modal = ({
  open,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnBackdrop = true,
}: ModalProps) => {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose]
  )

  useEffect(() => {
    if (!open) return
    document.addEventListener('keydown', handleKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = ''
    }
  }, [open, handleKey])

  if (!open) return null

  return createPortal(
    <div
      className="modal-backdrop"
      onClick={closeOnBackdrop ? onClose : undefined}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      <div
        className={clsx('modal-box')}
        style={{ maxWidth: sizeWidths[size] }}
        onClick={e => e.stopPropagation()}
      >
        {(title !== undefined) && (
          <div className="modal-header">
            <h2 id="modal-title" className="modal-title">{title}</h2>
            <button className="modal-close" onClick={onClose} aria-label="Закрыть">
              <X size={18} />
            </button>
          </div>
        )}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>

      <style>{`
        .modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,.45);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 16px;
          animation: fadeIn 0.15s ease;
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .modal-box {
          background: var(--color-surface);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-md);
          width: 100%;
          display: flex;
          flex-direction: column;
          max-height: calc(100vh - 48px);
          animation: slideUp 0.18s ease;
        }
        @keyframes slideUp {
          from { transform: translateY(12px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .modal-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px 24px 0;
        }
        .modal-title {
          font-size: 17px;
          font-weight: 600;
          color: var(--color-text);
        }
        .modal-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          transition: background 0.15s;
        }
        .modal-close:hover { background: var(--color-bg); color: var(--color-text); }
        .modal-body {
          padding: 20px 24px;
          overflow-y: auto;
          flex: 1;
        }
        .modal-footer {
          padding: 0 24px 20px;
          display: flex;
          justify-content: flex-end;
          gap: 8px;
        }
      `}</style>
    </div>,
    document.body
  )
}
