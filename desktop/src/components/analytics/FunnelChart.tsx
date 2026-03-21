import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { FunnelStage } from '@/api/analytics'

interface FunnelChartProps {
  stages: FunnelStage[]
}

const STAGE_COLORS = ['#3b82f6', '#f59e0b', '#22c55e', '#8b5cf6', '#ef4444', '#06b6d4']

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ value: number; payload: FunnelStage }>
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (!active || !payload?.length) return null
  const data = payload[0]!
  return (
    <div className="ftip">
      <div className="ftip-name">{data.payload.stage_name}</div>
      <div className="ftip-count">{data.value.toLocaleString('ru-RU')} кандидатов</div>
      {data.payload.conversion < 100 && (
        <div className="ftip-conv">Конверсия: {data.payload.conversion.toFixed(1)}%</div>
      )}
      <style>{`
        .ftip {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          padding: 10px 14px;
          box-shadow: var(--shadow-sm);
        }
        .ftip-name { font-size: 13px; font-weight: 600; color: var(--color-text); margin-bottom: 4px; }
        .ftip-count { font-size: 14px; font-weight: 700; color: var(--color-primary); }
        .ftip-conv { font-size: 12px; color: var(--color-text-secondary); margin-top: 3px; }
      `}</style>
    </div>
  )
}

export const FunnelChart = ({ stages }: FunnelChartProps) => {
  if (stages.length === 0) {
    return (
      <div className="fchart-empty">Нет данных для воронки</div>
    )
  }

  return (
    <div className="fchart">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={stages}
          layout="vertical"
          margin={{ top: 0, right: 60, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--color-border)" />
          <XAxis
            type="number"
            tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            dataKey="stage_name"
            type="category"
            width={120}
            tick={{ fontSize: 13, fill: 'var(--color-text)' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(59,130,246,.05)' }} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={32}>
            {stages.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={STAGE_COLORS[index % STAGE_COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <style>{`
        .fchart { width: 100%; }
        .fchart-empty {
          padding: 40px;
          text-align: center;
          font-size: 14px;
          color: var(--color-text-secondary);
        }
      `}</style>
    </div>
  )
}
