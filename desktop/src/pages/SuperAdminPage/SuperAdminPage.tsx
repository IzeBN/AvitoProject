import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useIsSuperAdmin } from '@/hooks/usePermission'
import OrganizationsTab from './OrganizationsTab'
import ErrorsTab from './ErrorsTab'
import StatsTab from './StatsTab'
import MailingsTab from './MailingsTab'
import clsx from 'clsx'

type Tab = 'stats' | 'organizations' | 'mailings' | 'errors'

const TABS: { id: Tab; label: string }[] = [
  { id: 'stats', label: 'Статистика' },
  { id: 'organizations', label: 'Организации' },
  { id: 'mailings', label: 'Рассылки' },
  { id: 'errors', label: 'Ошибки' },
]

export default function SuperAdminPage() {
  const isSuperAdmin = useIsSuperAdmin()
  const [activeTab, setActiveTab] = useState<Tab>('stats')

  if (!isSuperAdmin) return <Navigate to="/" replace />

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700 }}>Панель супер-администратора</h1>

      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={clsx('sa-tab', activeTab === tab.id && 'sa-tab--active')}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'stats' && <StatsTab />}
      {activeTab === 'organizations' && <OrganizationsTab />}
      {activeTab === 'mailings' && <MailingsTab />}
      {activeTab === 'errors' && <ErrorsTab />}

      <style>{`
        .sa-tab {
          padding: 10px 18px;
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text-secondary);
          border-bottom: 2px solid transparent;
          margin-bottom: -1px;
          transition: color 0.15s, border-color 0.15s;
        }
        .sa-tab:hover { color: var(--color-text); }
        .sa-tab--active { color: #7c3aed; border-bottom-color: #7c3aed; }
      `}</style>
    </div>
  )
}
