import { Bell } from 'lucide-react'
import { useAuthStore } from '@/stores/auth.store'

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Суперадмин',
  owner:      'Владелец',
  admin:      'Администратор',
  manager:    'Менеджер',
}

export const Header = () => {
  const user = useAuthStore(s => s.user)

  const roleLabel = user?.role ? (ROLE_LABELS[user.role] ?? user.role) : null

  return (
    <header className="header">
      {/* Организация + роль */}
      {user && (
        <div className="header-org">
          {user.org_name && (
            <span className="header-org-name">{user.org_name}</span>
          )}
          {roleLabel && (
            <span className="header-org-role">{roleLabel}</span>
          )}
        </div>
      )}

      <div className="header-spacer" />

      <div className="header-right">
        <button className="header-icon-btn" aria-label="Уведомления">
          <Bell size={18} />
        </button>
        <div className="header-avatar" title={user?.full_name}>
          {user?.full_name?.charAt(0).toUpperCase() ?? '?'}
        </div>
      </div>

      <style>{`
        .header {
          height: 56px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          display: flex;
          align-items: center;
          padding: 0 20px;
          flex-shrink: 0;
          gap: 12px;
        }
        .header-org {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .header-org-name {
          font-size: 14px;
          font-weight: 600;
          color: var(--color-text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 260px;
        }
        .header-org-role {
          font-size: 11px;
          font-weight: 500;
          color: var(--color-text-secondary);
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 4px;
          padding: 2px 7px;
          white-space: nowrap;
        }
        .header-spacer { flex: 1; }
        .header-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .header-icon-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 34px;
          height: 34px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
        }
        .header-icon-btn:hover { background: var(--color-bg); color: var(--color-text); }
        .header-avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--color-primary);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          font-weight: 600;
          user-select: none;
        }
      `}</style>
    </header>
  )
}
