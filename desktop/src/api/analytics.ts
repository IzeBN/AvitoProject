import { apiClient } from './client'

export interface FunnelStage {
  stage_id: string
  stage_name: string
  count: number
  conversion: number
}

export interface AnalyticsStats {
  total_candidates: number
  new_today: number
  active_chats: number
  mailings_sent: number
  funnel: FunnelStage[]
  period_from: string
  period_to: string
}

export interface AnalyticsFilters {
  period_from?: string
  period_to?: string
  department_id?: string
  responsible_id?: string
}

export const analyticsApi = {
  getStats: async (filters: AnalyticsFilters): Promise<AnalyticsStats> => {
    const params = {
      date_from: filters.period_from,
      date_to: filters.period_to,
      department_id: filters.department_id,
    }

    const [overviewRes, funnelRes] = await Promise.all([
      apiClient.get<{
        total_candidates: number
        new_this_week: number
        by_stage: Array<{ stage: string; count: number }>
      }>('/analytics/overview', { params }),
      apiClient.get<{
        stages: Array<{ name: string; count: number; conversion_from_prev: number | null }>
      }>('/analytics/funnel', { params }),
    ])

    const overview = overviewRes.data
    const funnelStages = funnelRes.data.stages ?? []
    const total = overview.total_candidates || 1

    const funnel: FunnelStage[] = funnelStages.map((s, i) => ({
      stage_id: String(i),
      stage_name: s.name,
      count: s.count,
      conversion: s.conversion_from_prev ?? (i === 0 ? 100 : 0),
    }))

    return {
      total_candidates: overview.total_candidates,
      new_today: overview.new_this_week,
      active_chats: 0,
      mailings_sent: 0,
      funnel,
      period_from: filters.period_from ?? '',
      period_to: filters.period_to ?? '',
    }
  },

  getDailyActivity: (filters: AnalyticsFilters) =>
    apiClient
      .get<Array<{ date: string; messages_count: number; changes_count: number; total: number }>>(
        '/analytics/activity',
        {
          params: {
            date_from: filters.period_from,
            date_to: filters.period_to,
          },
        }
      )
      .then(r =>
        r.data.map(item => ({
          date: typeof item.date === 'string' ? item.date : String(item.date),
          created: item.changes_count,
          messaged: item.messages_count,
        }))
      ),
}
