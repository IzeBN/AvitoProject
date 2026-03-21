import { useQuery } from '@tanstack/react-query'
import { superadminApi } from '@/api/superadmin'
import { Spinner } from '@/components/ui/Spinner'

interface StatCard {
  label: string
  value: number
  sublabel: string
  subvalue: number | string
  color: string
}

export default function StatsTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['superadmin', 'stats'],
    queryFn: () => superadminApi.getStats(),
    staleTime: 30_000,
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
        <Spinner />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div style={{ color: 'var(--color-danger)', fontSize: 14, padding: 16 }}>
        Не удалось загрузить статистику
      </div>
    )
  }

  const cards: StatCard[] = [
    {
      label: 'Организаций',
      value: data.total_orgs,
      sublabel: 'активных',
      subvalue: data.active_orgs,
      color: '#7c3aed',
    },
    {
      label: 'Пользователей',
      value: data.total_users,
      sublabel: 'заморожено',
      subvalue: data.suspended_orgs,
      color: 'var(--color-primary)',
    },
    {
      label: 'Рассылок',
      value: data.mailings_today,
      sublabel: 'активных сейчас',
      subvalue: data.active_mailings,
      color: 'var(--color-warning)',
    },
    {
      label: 'Ошибок',
      value: data.errors_today,
      sublabel: 'нерешённых',
      subvalue: data.unresolved_errors,
      color: 'var(--color-danger)',
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {cards.map(card => (
          <div
            key={card.label}
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              padding: '20px 24px',
              borderLeft: `4px solid ${card.color}`,
            }}
          >
            <div style={{ fontSize: 32, fontWeight: 700, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)', marginTop: 2 }}>
              {card.label}
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--color-text-secondary)',
                marginTop: 6,
              }}
            >
              {card.sublabel}: <strong>{card.subvalue}</strong>
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
        Автообновление каждые 30 секунд
      </div>
    </div>
  )
}
