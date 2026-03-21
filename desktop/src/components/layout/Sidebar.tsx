import { NavLink, useNavigate } from 'react-router-dom'
import {
  Users,
  MessageSquare,
  Send,
  CheckSquare,
  BarChart2,
  Briefcase,
  SmartphoneNfc,
  Bot,
  FileText,
  UserCog,
  Settings,
  Shield,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from 'lucide-react'
import clsx from 'clsx'
import { useUIStore } from '@/stores/ui.store'
import { useAuthStore } from '@/stores/auth.store'
import { useIsSuperAdmin } from '@/hooks/usePermission'

interface NavItem {
  to: string
  label: string
  icon: React.ReactNode
  /** permission code; если не указан — вкладка видна всем авторизованным */
  permission?: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/candidates',     label: 'Кандидаты',      icon: <Users size={18} />,         permission: 'crm.candidates.view'     },
  { to: '/messenger',      label: 'Мессенджер',     icon: <MessageSquare size={18} />,  permission: 'messaging.view'          },
  { to: '/mailings',       label: 'Рассылки',       icon: <Send size={18} />,           permission: 'mailing.view'            },
  { to: '/tasks',          label: 'Задачи',         icon: <CheckSquare size={18} />                                           },
  { to: '/analytics',      label: 'Аналитика',      icon: <BarChart2 size={18} />,      permission: 'analytics.view'          },
  { to: '/vacancies',      label: 'Вакансии',       icon: <Briefcase size={18} />,      permission: 'vacancies.view'          },
  { to: '/avito-accounts', label: 'Авито аккаунты', icon: <SmartphoneNfc size={18} />,  permission: 'avito.accounts.view'     },
  { to: '/auto-response',  label: 'Автоответы',     icon: <Bot size={18} />,            permission: 'messaging.auto_response' },
  { to: '/self-employed',  label: 'Самозанятые',    icon: <FileText size={18} />,       permission: 'self_employed.check'     },
  { to: '/users',          label: 'Пользователи',   icon: <UserCog size={18} />,        permission: 'admin.users.view'        },
  { to: '/settings',       label: 'Настройки',      icon: <Settings size={18} />,       permission: 'admin.settings.manage'   },
]

export const Sidebar = () => {
  const collapsed = useUIStore(s => s.sidebarCollapsed)
  const toggleSidebar = useUIStore(s => s.toggleSidebar)
  const isSuperAdmin = useIsSuperAdmin()
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const permissions = useAuthStore(s => s.permissions)

  const hasPermission = (code?: string) => {
    if (!code) return true
    if (permissions === 'all') return true
    if (!permissions) return false
    return permissions.includes(code)
  }

  const visibleItems = NAV_ITEMS.filter(item => hasPermission(item.permission))

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside
      className="sidebar"
      style={{ width: collapsed ? 60 : 220, minWidth: collapsed ? 60 : 220 }}
    >
      {/* Логотип */}
      <div className="sidebar-logo">
        {!collapsed && <span className="sidebar-logo-text">AvitoСRM</span>}
      </div>

      {/* Навигация */}
      <nav className="sidebar-nav" role="navigation" aria-label="Главное меню">
        {visibleItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx('sidebar-link', isActive && 'sidebar-link--active')
            }
            title={collapsed ? item.label : undefined}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            {!collapsed && <span className="sidebar-link-label">{item.label}</span>}
          </NavLink>
        ))}

        {isSuperAdmin && (
          <NavLink
            to="/superadmin"
            className={({ isActive }) =>
              clsx('sidebar-link sidebar-link--superadmin', isActive && 'sidebar-link--active')
            }
            title={collapsed ? 'Супер-админ' : undefined}
          >
            <span className="sidebar-link-icon"><Shield size={18} /></span>
            {!collapsed && <span className="sidebar-link-label">Супер-админ</span>}
          </NavLink>
        )}
      </nav>

      {/* Кнопка выхода */}
      <div className="sidebar-bottom">
        <button
          className="sidebar-link sidebar-logout"
          onClick={handleLogout}
          title={collapsed ? 'Выйти' : undefined}
        >
          <span className="sidebar-link-icon"><LogOut size={18} /></span>
          {!collapsed && <span className="sidebar-link-label">Выйти</span>}
        </button>

        {/* Toggle collapse */}
        <button
          className="sidebar-toggle"
          onClick={toggleSidebar}
          aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <style>{`
        .sidebar {
          width: 220px;
          min-width: 220px;
          background: var(--color-surface);
          border-right: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          transition: width 0.2s, min-width 0.2s;
          overflow: hidden;
        }
        .sidebar--collapsed {
          width: 60px;
          min-width: 60px;
        }
        .sidebar-logo {
          height: 56px;
          display: flex;
          align-items: center;
          padding: 0 16px;
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .sidebar-logo-text {
          font-size: 16px;
          font-weight: 700;
          color: var(--color-primary);
          white-space: nowrap;
        }
        .sidebar-nav {
          flex: 1;
          padding: 8px 0;
          overflow-y: auto;
          overflow-x: hidden;
        }
        .sidebar-link {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 9px 16px;
          color: var(--color-text-secondary);
          font-size: 14px;
          font-weight: 500;
          transition: background 0.12s, color 0.12s;
          white-space: nowrap;
          width: 100%;
          text-align: left;
        }
        .sidebar-link:hover {
          background: var(--color-bg);
          color: var(--color-text);
        }
        .sidebar-link--active {
          background: #eff6ff;
          color: var(--color-primary);
        }
        .sidebar-link--superadmin { color: #7c3aed; }
        .sidebar-link--superadmin.sidebar-link--active {
          background: #f5f3ff;
          color: #7c3aed;
        }
        .sidebar-link-icon {
          display: flex;
          align-items: center;
          flex-shrink: 0;
        }
        .sidebar-link-label { overflow: hidden; text-overflow: ellipsis; }
        .sidebar-bottom {
          padding: 8px 0;
          border-top: 1px solid var(--color-border);
        }
        .sidebar-logout { width: 100%; }
        .sidebar-logout:hover { background: #fff0f0; color: var(--color-danger); }
        .sidebar-toggle {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          padding: 8px;
          color: var(--color-text-secondary);
          font-size: 12px;
          gap: 6px;
        }
        .sidebar-toggle:hover { background: var(--color-bg); }
        /* Responsive */
        @media (max-width: 900px) {
          .sidebar { width: 60px; min-width: 60px; }
          .sidebar-logo-text { display: none; }
          .sidebar-link-label { display: none; }
        }
        @media (min-width: 1400px) {
          .sidebar { width: 240px; min-width: 240px; }
        }
      `}</style>
    </aside>
  )
}
