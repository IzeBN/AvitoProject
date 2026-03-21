import { useNavigate } from 'react-router-dom'
import { useLogout } from '@/hooks/useAuth'
import { useAuthStore } from '@/stores/auth.store'
import { UserX, Clock, RefreshCw, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/Button'

type Reason = 'no_org' | 'suspended' | 'expired'

interface NoOrgPageProps {
  reason?: Reason
}

const CONTENT = {
  no_org: {
    title: 'Вы не привязаны к организации',
    description:
      'Ваш аккаунт создан, но ещё не добавлен в организацию. Обратитесь к своему руководителю или свяжитесь с нами для подключения вашей компании.',
  },
  suspended: {
    title: 'Доступ временно ограничен',
    description:
      'Доступ к вашей организации временно ограничен администратором. Обратитесь в поддержку.',
  },
  expired: {
    title: 'Подписка истекла',
    description:
      'Срок действия подписки вашей организации истёк. Обратитесь к владельцу аккаунта для продления.',
  },
} satisfies Record<Reason, { title: string; description: string }>

export const NoOrgPage = ({ reason = 'no_org' }: NoOrgPageProps) => {
  const logout = useLogout()
  const navigate = useNavigate()
  const refresh = useAuthStore(s => s.refresh)
  const { title, description } = CONTENT[reason]
  const isNoOrg = reason === 'no_org'

  const handleRefresh = async () => {
    try {
      await refresh()
      navigate('/', { replace: true })
    } catch {
      // токен истёк — выходим
      await logout()
    }
  }

  return (
    <div className="noorg-page">
      <div className="noorg-card">
        <div className="noorg-icon-wrap">
          {isNoOrg ? (
            <UserX size={48} color="#f97316" strokeWidth={1.5} />
          ) : (
            <Clock size={48} color="#ef4444" strokeWidth={1.5} />
          )}
        </div>

        <h1 className="noorg-title">{title}</h1>
        <p className="noorg-description">{description}</p>

        {isNoOrg && (
          <div className="noorg-contact-box">
            <span className="noorg-contact-label">Связаться с нами:</span>
            <span className="noorg-contact-email">
              <span aria-hidden="true">📧</span>{' '}
              <a href="mailto:support@avitocrm.ru">support@avitocrm.ru</a>
            </span>
          </div>
        )}

        <div className="noorg-actions">
          <Button
            variant="primary"
            size="md"
            onClick={() => void handleRefresh()}
          >
            <RefreshCw size={15} />
            Обновить статус
          </Button>

          <Button
            variant="secondary"
            size="md"
            onClick={logout}
          >
            <LogOut size={15} />
            Выйти
          </Button>
        </div>
      </div>

      <style>{`
        .noorg-page {
          width: 100%;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          background: var(--color-bg);
        }
        .noorg-card {
          width: 100%;
          max-width: 500px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: 48px 40px;
          box-shadow: var(--shadow-md);
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 20px;
        }
        .noorg-icon-wrap {
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .noorg-title {
          font-size: 22px;
          font-weight: 700;
          color: var(--color-text);
          margin: 0;
        }
        .noorg-description {
          font-size: 14px;
          color: var(--color-text-secondary);
          line-height: 1.6;
          margin: 0;
          max-width: 380px;
        }
        .noorg-contact-box {
          width: 100%;
          background: #eff6ff;
          border: 1px solid #bfdbfe;
          border-radius: var(--radius-md);
          padding: 14px 18px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          text-align: left;
        }
        .noorg-contact-label {
          font-size: 13px;
          font-weight: 600;
          color: #1d4ed8;
        }
        .noorg-contact-email {
          font-size: 13px;
          color: #1e40af;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .noorg-contact-email a {
          color: inherit;
          text-decoration: none;
        }
        .noorg-contact-email a:hover {
          text-decoration: underline;
        }
        .noorg-actions {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          justify-content: center;
          margin-top: 4px;
        }
      `}</style>
    </div>
  )
}
