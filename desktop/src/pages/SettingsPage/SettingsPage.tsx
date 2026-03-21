import { NavLink, Routes, Route, Navigate } from 'react-router-dom'
import clsx from 'clsx'
import StagesSettings from './StagesSettings'
import TagsSettings from './TagsSettings'
import DepartmentsSettings from './DepartmentsSettings'
import PermissionsSettings from './PermissionsSettings'

const TABS = [
  { to: 'stages', label: 'Этапы' },
  { to: 'tags', label: 'Теги' },
  { to: 'departments', label: 'Отделы' },
  { to: 'permissions', label: 'Права ролей' },
]

export default function SettingsPage() {
  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700 }}>Настройки</h1>

      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--color-border)' }}>
        {TABS.map(tab => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              clsx('settings-tab', isActive && 'settings-tab--active')
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </div>

      <Routes>
        <Route index element={<Navigate to="stages" replace />} />
        <Route path="stages" element={<StagesSettings />} />
        <Route path="tags" element={<TagsSettings />} />
        <Route path="departments" element={<DepartmentsSettings />} />
        <Route path="permissions" element={<PermissionsSettings />} />
      </Routes>

      <style>{`
        .settings-tab {
          padding: 10px 18px;
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text-secondary);
          border-bottom: 2px solid transparent;
          margin-bottom: -1px;
          transition: color 0.15s, border-color 0.15s;
        }
        .settings-tab:hover { color: var(--color-text); }
        .settings-tab--active {
          color: var(--color-primary);
          border-bottom-color: var(--color-primary);
        }
      `}</style>
    </div>
  )
}
