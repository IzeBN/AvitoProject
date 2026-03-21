import { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { useAnalyticsStats, useAnalyticsDailyActivity } from '@/hooks/useAnalytics'
import { Spinner } from '@/components/ui/Spinner'
import { StatsCards } from '@/components/analytics/StatsCards'
import { FunnelChart } from '@/components/analytics/FunnelChart'
import type { AnalyticsFilters } from '@/api/analytics'

type PeriodPreset = '7d' | '30d' | '90d' | 'custom'

const PERIOD_PRESETS: Array<{ key: PeriodPreset; label: string; days?: number }> = [
  { key: '7d', label: '7 дней', days: 7 },
  { key: '30d', label: '30 дней', days: 30 },
  { key: '90d', label: '90 дней', days: 90 },
  { key: 'custom', label: 'Произвольный' },
]

const toISO = (d: Date) => d.toISOString().split('T')[0]

const subtractDays = (days: number) => {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return toISO(d)
}

const formatDay = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

export default function AnalyticsPage() {
  const today = toISO(new Date())
  const [preset, setPreset] = useState<PeriodPreset>('30d')
  const [customFrom, setCustomFrom] = useState(subtractDays(30))
  const [customTo, setCustomTo] = useState(today)

  const filters = useMemo<AnalyticsFilters>(() => {
    if (preset === 'custom') {
      return { period_from: customFrom, period_to: customTo }
    }
    const days = PERIOD_PRESETS.find(p => p.key === preset)?.days ?? 30
    return { period_from: subtractDays(days), period_to: today }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset, customFrom, customTo])

  const { data: stats, isLoading: statsLoading } = useAnalyticsStats(filters)
  const { data: daily = [], isLoading: dailyLoading } = useAnalyticsDailyActivity(filters)

  return (
    <div className="ap-page">
      {/* Заголовок + фильтры */}
      <div className="ap-header">
        <h1 className="ap-title">Аналитика</h1>
        <div className="ap-period">
          {PERIOD_PRESETS.map(p => (
            <button
              key={p.key}
              className={`ap-period-btn ${preset === p.key ? 'ap-period-btn--active' : ''}`}
              onClick={() => setPreset(p.key)}
            >
              {p.label}
            </button>
          ))}
          {preset === 'custom' && (
            <div className="ap-custom-range">
              <input
                type="date"
                className="ap-date-input"
                value={customFrom}
                max={customTo}
                onChange={e => setCustomFrom(e.target.value)}
              />
              <span className="ap-date-sep">—</span>
              <input
                type="date"
                className="ap-date-input"
                value={customTo}
                min={customFrom}
                max={today}
                onChange={e => setCustomTo(e.target.value)}
              />
            </div>
          )}
        </div>
      </div>

      <div className="ap-body">
        {/* Карточки статистики */}
        {statsLoading ? (
          <div className="ap-loading"><Spinner size="lg" /></div>
        ) : stats ? (
          <StatsCards stats={stats} />
        ) : null}

        {/* Активность по дням (LineChart) */}
        <div className="ap-card">
          <h2 className="ap-card-title">
            Активность кандидатов за {PERIOD_PRESETS.find(p => p.key === preset)?.label ?? 'период'}
          </h2>
          {dailyLoading ? (
            <div className="ap-card-loading"><Spinner size="md" /></div>
          ) : daily.length === 0 ? (
            <div className="ap-card-empty">Нет данных за выбранный период</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={daily} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDay}
                  tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
                  interval="preserveStartEnd"
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={formatDay}
                  formatter={(value: number, name: string) => [
                    value.toLocaleString('ru-RU'),
                    name === 'created' ? 'Новых кандидатов' : 'С сообщениями',
                  ]}
                  contentStyle={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    fontSize: 13,
                  }}
                />
                <Legend
                  formatter={(value) => value === 'created' ? 'Новых кандидатов' : 'С сообщениями'}
                  wrapperStyle={{ fontSize: 12 }}
                />
                <Line
                  type="monotone"
                  dataKey="created"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="messaged"
                  stroke="var(--color-success)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Воронка этапов */}
        {stats && (
          <div className="ap-card">
            <h2 className="ap-card-title">Воронка этапов</h2>
            <FunnelChart stages={stats.funnel} />
          </div>
        )}

        {/* Итоговая таблица по этапам */}
        {stats?.funnel && stats.funnel.length > 0 && (
          <div className="ap-card">
            <h2 className="ap-card-title">Распределение по этапам</h2>
            <div className="ap-table-wrap">
              <table className="ap-table">
                <thead>
                  <tr>
                    <th className="ap-th">Этап</th>
                    <th className="ap-th ap-th--right">Кандидатов</th>
                    <th className="ap-th ap-th--right">Конверсия, %</th>
                    <th className="ap-th" style={{ width: '40%' }}>Доля</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.funnel.map(stage => {
                    const maxCount = Math.max(...stats.funnel.map(s => s.count), 1)
                    const barWidth = (stage.count / maxCount) * 100
                    return (
                      <tr key={stage.stage_id} className="ap-tr">
                        <td className="ap-td ap-td--name">{stage.stage_name}</td>
                        <td className="ap-td ap-td--right ap-td--num">
                          {stage.count.toLocaleString('ru-RU')}
                        </td>
                        <td className="ap-td ap-td--right">
                          <span className={`ap-conv ${stage.conversion < 50 ? 'ap-conv--low' : ''}`}>
                            {stage.conversion.toFixed(1)}%
                          </span>
                        </td>
                        <td className="ap-td">
                          <div className="ap-bar-track">
                            <div
                              className="ap-bar-fill"
                              style={{ width: `${barWidth}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <style>{`
        .ap-page {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .ap-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px 24px 16px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          flex-shrink: 0;
          flex-wrap: wrap;
          gap: 12px;
        }
        .ap-title { font-size: 20px; font-weight: 700; }
        .ap-period {
          display: flex;
          align-items: center;
          gap: 4px;
          flex-wrap: wrap;
        }
        .ap-period-btn {
          padding: 6px 14px;
          border-radius: var(--radius-sm);
          font-size: 13px;
          font-weight: 500;
          color: var(--color-text-secondary);
          border: 1px solid transparent;
          transition: all 0.15s;
        }
        .ap-period-btn:hover { background: var(--color-bg); color: var(--color-text); }
        .ap-period-btn--active {
          background: var(--color-primary);
          color: #fff;
          border-color: var(--color-primary);
        }
        .ap-custom-range {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-left: 8px;
        }
        .ap-date-input {
          padding: 6px 10px;
          font-size: 13px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
        }
        .ap-date-input:focus { border-color: var(--color-primary); }
        .ap-date-sep { color: var(--color-text-secondary); }
        .ap-body {
          flex: 1;
          overflow-y: auto;
          padding: 20px 24px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        .ap-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 60px;
        }
        .ap-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          padding: 20px 24px;
        }
        .ap-card-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--color-text);
          margin-bottom: 18px;
        }
        .ap-card-loading, .ap-card-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px;
          font-size: 14px;
          color: var(--color-text-secondary);
        }
        .ap-table-wrap { overflow-x: auto; }
        .ap-table { width: 100%; border-collapse: collapse; font-size: 14px; }
        .ap-th {
          padding: 8px 12px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
          border-bottom: 1px solid var(--color-border);
          background: var(--color-bg);
          white-space: nowrap;
        }
        .ap-th--right { text-align: right; }
        .ap-tr:hover .ap-td { background: var(--color-bg); }
        .ap-td {
          padding: 10px 12px;
          border-bottom: 1px solid var(--color-border);
          color: var(--color-text);
        }
        .ap-td--right { text-align: right; }
        .ap-td--name { font-weight: 500; }
        .ap-td--num { font-weight: 600; font-size: 15px; }
        .ap-conv { font-weight: 500; color: var(--color-success); }
        .ap-conv--low { color: var(--color-warning); }
        .ap-bar-track {
          height: 8px;
          background: var(--color-border);
          border-radius: 999px;
          overflow: hidden;
        }
        .ap-bar-fill {
          height: 100%;
          background: var(--color-primary);
          border-radius: 999px;
          transition: width 0.4s ease;
        }
      `}</style>
    </div>
  )
}
