import { useRef, useEffect, type RefObject } from 'react'
import { useQuery } from '@tanstack/react-query'
import { chatApi } from '@/api/chat'
import { Spinner } from '@/components/ui/Spinner'
import { Zap } from 'lucide-react'

interface FastAnswersPopoverProps {
  open: boolean
  onClose: () => void
  onSelect: (text: string) => void
  anchorRef: RefObject<HTMLButtonElement>
}

export const FastAnswersPopover = ({
  open,
  onClose,
  onSelect,
  anchorRef,
}: FastAnswersPopoverProps) => {
  const popoverRef = useRef<HTMLDivElement>(null)
  const { data: answers = [], isLoading } = useQuery({
    queryKey: ['fast-answers'],
    queryFn: () => chatApi.getFastAnswers(),
    staleTime: 60_000,
    enabled: open,
  })

  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        anchorRef.current &&
        !anchorRef.current.contains(e.target as Node)
      ) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open, onClose, anchorRef])

  if (!open) return null

  return (
    <div className="fa-popover" ref={popoverRef} role="listbox" aria-label="Быстрые ответы">
      <div className="fa-header">
        <Zap size={14} />
        <span>Быстрые ответы</span>
      </div>

      {isLoading ? (
        <div className="fa-loading"><Spinner size="sm" /></div>
      ) : answers.length === 0 ? (
        <div className="fa-empty">Нет быстрых ответов</div>
      ) : (
        <ul className="fa-list">
          {answers.map(a => (
            <li key={a.id}>
              <button
                className="fa-item"
                onClick={() => { onSelect(a.text); onClose() }}
                role="option"
              >
                <span className="fa-item-title">{a.title}</span>
                <span className="fa-item-text">{a.text}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <style>{`
        .fa-popover {
          position: absolute;
          bottom: calc(100% + 8px);
          left: 0;
          min-width: 320px;
          width: max-content;
          max-width: min(480px, 90vw);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          box-shadow: var(--shadow-md);
          z-index: 100;
          max-height: 280px;
          overflow-y: auto;
          animation: fadeIn 0.15s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
        .fa-header {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 10px 14px 8px;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-secondary);
          border-bottom: 1px solid var(--color-border);
          position: sticky;
          top: 0;
          background: var(--color-surface);
        }
        .fa-loading, .fa-empty {
          padding: 16px;
          text-align: center;
          font-size: 13px;
          color: var(--color-text-secondary);
        }
        .fa-list { list-style: none; }
        .fa-item {
          width: 100%;
          text-align: left;
          padding: 10px 14px;
          display: flex;
          flex-direction: column;
          gap: 2px;
          transition: background 0.1s;
        }
        .fa-item:hover { background: var(--color-bg); }
        .fa-item-title {
          font-size: 13px;
          font-weight: 500;
          color: var(--color-text);
        }
        .fa-item-text {
          font-size: 12px;
          color: var(--color-text-secondary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      `}</style>
    </div>
  )
}
