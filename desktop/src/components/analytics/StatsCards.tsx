import { Users, UserPlus, MessageCircle, TrendingUp } from 'lucide-react'
import type { AnalyticsStats } from '@/api/analytics'

interface StatsCardsProps {
  stats: AnalyticsStats
}

export const StatsCards = ({ stats }: StatsCardsProps) => {
  const cards = [
    {
      label: 'Всего кандидатов',
      value: stats.total_candidates.toLocaleString('ru-RU'),
      icon: <Users size={20} />,
      color: 'var(--color-primary)',
      bg: '#eff6ff',
    },
    {
      label: 'Новых за 7 дней',
      value: stats.new_today.toLocaleString('ru-RU'),
      icon: <UserPlus size={20} />,
      color: 'var(--color-success)',
      bg: '#f0fdf4',
    },
    {
      label: 'Активных чатов',
      value: stats.active_chats.toLocaleString('ru-RU'),
      icon: <MessageCircle size={20} />,
      color: 'var(--color-warning)',
      bg: '#fffbeb',
    },
    {
      label: 'Рассылок отправлено',
      value: stats.mailings_sent.toLocaleString('ru-RU'),
      icon: <TrendingUp size={20} />,
      color: '#8b5cf6',
      bg: '#f5f3ff',
    },
  ]

  return (
    <div className="stats-cards">
      {cards.map(card => (
        <div key={card.label} className="stats-card">
          <div className="stats-card-icon" style={{ background: card.bg, color: card.color }}>
            {card.icon}
          </div>
          <div className="stats-card-body">
            <div className="stats-card-value">{card.value}</div>
            <div className="stats-card-label">{card.label}</div>
          </div>
        </div>
      ))}

      <style>{`
        .stats-cards {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
        }
        @media (max-width: 900px) {
          .stats-cards { grid-template-columns: repeat(2, 1fr); }
        }
        .stats-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          padding: 16px 20px;
          display: flex;
          align-items: center;
          gap: 14px;
          transition: box-shadow 0.15s;
        }
        .stats-card:hover { box-shadow: var(--shadow-sm); }
        .stats-card-icon {
          width: 44px;
          height: 44px;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .stats-card-value {
          font-size: 24px;
          font-weight: 700;
          color: var(--color-text);
          line-height: 1.2;
        }
        .stats-card-label {
          font-size: 13px;
          color: var(--color-text-secondary);
          margin-top: 2px;
        }
      `}</style>
    </div>
  )
}
