import { X, GitBranch, UserCheck, Tag, Send } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface BulkActionsBarProps {
  selectedCount: number
  onClearSelection: () => void
  onChangeStage: () => void
  onAssignResponsible: () => void
  onAddTag: () => void
  onStartMailing: () => void
}

export const BulkActionsBar = ({
  selectedCount,
  onClearSelection,
  onChangeStage,
  onAssignResponsible,
  onAddTag,
  onStartMailing,
}: BulkActionsBarProps) => {
  if (selectedCount === 0) return null

  return (
    <div className="bulk-bar" role="toolbar" aria-label="Массовые действия">
      <div className="bulk-bar-left">
        <button className="bulk-bar-close" onClick={onClearSelection} aria-label="Снять выделение">
          <X size={16} />
        </button>
        <span className="bulk-bar-count">
          Выбрано: <strong>{selectedCount}</strong>
        </span>
      </div>

      <div className="bulk-bar-actions">
        <Button
          variant="secondary"
          size="sm"
          icon={<GitBranch size={14} />}
          onClick={onChangeStage}
        >
          Сменить этап
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={<UserCheck size={14} />}
          onClick={onAssignResponsible}
        >
          Назначить ответственного
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={<Tag size={14} />}
          onClick={onAddTag}
        >
          Добавить тег
        </Button>
        <Button
          variant="primary"
          size="sm"
          icon={<Send size={14} />}
          onClick={onStartMailing}
        >
          Начать рассылку
        </Button>
      </div>

      <style>{`
        .bulk-bar {
          position: fixed;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          align-items: center;
          gap: 12px;
          background: var(--color-text);
          color: #fff;
          border-radius: var(--radius-lg);
          padding: 12px 20px;
          box-shadow: var(--shadow-md);
          z-index: 500;
          animation: slideUp 0.2s ease;
          white-space: nowrap;
        }
        @keyframes slideUp {
          from { transform: translateX(-50%) translateY(20px); opacity: 0; }
          to { transform: translateX(-50%) translateY(0); opacity: 1; }
        }
        .bulk-bar-left {
          display: flex;
          align-items: center;
          gap: 10px;
          padding-right: 12px;
          border-right: 1px solid rgba(255,255,255,.2);
        }
        .bulk-bar-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          color: rgba(255,255,255,.7);
          transition: color 0.15s, background 0.15s;
        }
        .bulk-bar-close:hover { color: #fff; background: rgba(255,255,255,.1); }
        .bulk-bar-count {
          font-size: 14px;
          color: rgba(255,255,255,.85);
        }
        .bulk-bar-count strong { color: #fff; }
        .bulk-bar-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }
      `}</style>
    </div>
  )
}
