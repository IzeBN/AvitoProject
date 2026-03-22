import { useState, useRef, useEffect } from 'react'
import { Bell, CheckCheck, ClipboardList, LogOut } from 'lucide-react'
import { useAuthStore } from '@/stores/auth.store'
import { useNotificationsStore } from '@/stores/notifications.store'
import { useNavigate } from 'react-router-dom'

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Суперадмин',
  owner:      'Владелец',
  admin:      'Администратор',
  manager:    'Менеджер',
}

export const Header = () => {
  const user = useAuthStore(s => s.user)
  const navigate = useNavigate()
  const { notifications, unread, markAllRead } = useNotificationsStore()
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef<HTMLDivElement>(null)

  const roleLabel = user?.role ? (ROLE_LABELS[user.role] ?? user.role) : null

  // Закрыть при клике вне панели уведомлений
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Закрыть при клике вне профильного дропдауна
  useEffect(() => {
    if (!profileOpen) return
    const handler = (e: MouseEvent) => {
      if (!profileRef.current?.contains(e.target as Node)) setProfileOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [profileOpen])

  const handleLogout = () => {
    setProfileOpen(false)
    useAuthStore.getState().logout()
    navigate('/login')
  }

  const handleBellClick = () => {
    setOpen(prev => !prev)
    if (!open && unread > 0) markAllRead()
  }

  const handleNotificationClick = (taskId?: string) => {
    setOpen(false)
    if (taskId) navigate('/tasks')
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

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
        {/* Колокольчик с уведомлениями */}
        <div ref={panelRef} style={{ position: 'relative' }}>
          <button
            className="header-icon-btn"
            aria-label="Уведомления"
            onClick={handleBellClick}
            style={{ position: 'relative' }}
          >
            <Bell size={18} />
            {unread > 0 && (
              <span className="header-notif-badge">{unread > 9 ? '9+' : unread}</span>
            )}
          </button>

          {open && (
            <div className="notif-panel">
              <div className="notif-panel-header">
                <span>Уведомления</span>
                {notifications.length > 0 && (
                  <button className="notif-clear-btn" onClick={() => useNotificationsStore.getState().clear()}>
                    Очистить
                  </button>
                )}
              </div>

              {notifications.length === 0 ? (
                <div className="notif-empty">
                  <CheckCheck size={28} style={{ opacity: 0.3 }} />
                  <span>Всё прочитано</span>
                </div>
              ) : (
                <div className="notif-list">
                  {notifications.map(n => (
                    <button
                      key={n.id}
                      className="notif-item"
                      onClick={() => handleNotificationClick(n.task_id)}
                    >
                      <div className="notif-item-icon">
                        <ClipboardList size={16} />
                      </div>
                      <div className="notif-item-content">
                        <div className="notif-item-title">{n.title}</div>
                        <div className="notif-item-body">{n.body}</div>
                        <div className="notif-item-time">{formatTime(n.created_at)}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div ref={profileRef} style={{ position: 'relative' }}>
          <button
            className="header-avatar"
            title={user?.full_name}
            onClick={() => setProfileOpen(prev => !prev)}
            aria-label="Профиль"
          >
            {user?.full_name?.charAt(0).toUpperCase() ?? '?'}
          </button>

          {profileOpen && (
            <div className="profile-dropdown">
              <div className="profile-dropdown-info">
                <div className="profile-dropdown-name">{user?.full_name ?? '—'}</div>
                <div className="profile-dropdown-email">{user?.email ?? ''}</div>
              </div>
              <div className="profile-dropdown-divider" />
              <button className="profile-dropdown-logout" onClick={handleLogout}>
                <LogOut size={14} />
                <span>Выйти</span>
              </button>
            </div>
          )}
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
        .header-notif-badge {
          position: absolute;
          top: 4px;
          right: 4px;
          min-width: 16px;
          height: 16px;
          padding: 0 4px;
          background: var(--color-danger);
          color: #fff;
          border-radius: 999px;
          font-size: 10px;
          font-weight: 700;
          display: flex;
          align-items: center;
          justify-content: center;
          line-height: 1;
          pointer-events: none;
        }
        .notif-panel {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          width: 320px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          box-shadow: var(--shadow-md);
          z-index: 200;
          overflow: hidden;
        }
        .notif-panel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          font-size: 13px;
          font-weight: 600;
          border-bottom: 1px solid var(--color-border);
        }
        .notif-clear-btn {
          font-size: 12px;
          color: var(--color-text-secondary);
          background: none;
          border: none;
          cursor: pointer;
          padding: 0;
        }
        .notif-clear-btn:hover { color: var(--color-text); }
        .notif-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          padding: 32px;
          color: var(--color-text-secondary);
          font-size: 13px;
        }
        .notif-list {
          max-height: 360px;
          overflow-y: auto;
        }
        .notif-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          padding: 12px 16px;
          width: 100%;
          text-align: left;
          border-bottom: 1px solid var(--color-border);
          transition: background 0.15s;
          cursor: pointer;
          background: none;
          border-left: none;
          border-right: none;
          border-top: none;
        }
        .notif-item:last-child { border-bottom: none; }
        .notif-item:hover { background: var(--color-bg); }
        .notif-item-icon {
          flex-shrink: 0;
          width: 28px;
          height: 28px;
          border-radius: var(--radius-sm);
          background: var(--color-primary);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-top: 2px;
        }
        .notif-item-content { flex: 1; min-width: 0; }
        .notif-item-title {
          font-size: 12px;
          font-weight: 600;
          color: var(--color-text);
          margin-bottom: 2px;
        }
        .notif-item-body {
          font-size: 12px;
          color: var(--color-text-secondary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .notif-item-time {
          font-size: 11px;
          color: var(--color-text-secondary);
          margin-top: 4px;
        }
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
          cursor: pointer;
          transition: opacity 0.15s;
        }
        .header-avatar:hover { opacity: 0.85; }
        .profile-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          width: 220px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          box-shadow: var(--shadow-md);
          z-index: 200;
          overflow: hidden;
        }
        .profile-dropdown-info {
          padding: 14px 16px 12px;
        }
        .profile-dropdown-name {
          font-size: 14px;
          font-weight: 700;
          color: var(--color-text);
          margin-bottom: 3px;
        }
        .profile-dropdown-email {
          font-size: 12px;
          color: var(--color-text-secondary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .profile-dropdown-divider {
          height: 1px;
          background: var(--color-border);
        }
        .profile-dropdown-logout {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          padding: 10px 16px;
          font-size: 13px;
          color: var(--color-danger);
          background: none;
          text-align: left;
          cursor: pointer;
          transition: background 0.15s;
        }
        .profile-dropdown-logout:hover { background: var(--color-bg); }
      `}</style>
    </header>
  )
}
