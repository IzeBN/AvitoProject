import { createPortal } from 'react-dom'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import { useUIStore, type Toast as ToastType } from '@/stores/ui.store'

const icons = {
  success: <CheckCircle size={16} />,
  error: <AlertCircle size={16} />,
  info: <Info size={16} />,
  warning: <AlertTriangle size={16} />,
}

const colors = {
  success: '#15803d',
  error: '#b91c1c',
  info: '#1d4ed8',
  warning: '#b45309',
}


function ToastItem({ toast }: { toast: ToastType }) {
  const removeToast = useUIStore(s => s.removeToast)
  return (
    <div
      className="toast-item"
      role="alert"
      style={{ borderLeft: `3px solid ${colors[toast.type]}` }}
    >
      <span style={{ color: colors[toast.type] }}>{icons[toast.type]}</span>
      <span className="toast-msg">{toast.message}</span>
      <button
        className="toast-close"
        onClick={() => removeToast(toast.id)}
        aria-label="Закрыть"
      >
        <X size={14} />
      </button>

      <style>{`
        .toast-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 14px;
          background: var(--color-surface);
          border-radius: var(--radius-md);
          box-shadow: var(--shadow-md);
          min-width: 280px;
          max-width: 420px;
          animation: toastIn 0.2s ease;
        }
        @keyframes toastIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .toast-msg { flex: 1; font-size: 14px; color: var(--color-text); }
        .toast-close {
          display: flex;
          align-items: center;
          color: var(--color-text-secondary);
          opacity: 0.6;
          padding: 2px;
        }
        .toast-close:hover { opacity: 1; }
      `}</style>
    </div>
  )
}

export const ToastContainer = () => {
  const toasts = useUIStore(s => s.toasts)

  if (toasts.length === 0) return null

  return createPortal(
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        zIndex: 2000,
      }}
    >
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>,
    document.body
  )
}
