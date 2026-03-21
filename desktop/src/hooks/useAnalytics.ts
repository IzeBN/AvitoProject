import { useQuery } from '@tanstack/react-query'
import { analyticsApi, type AnalyticsFilters } from '@/api/analytics'

export function useAnalyticsStats(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'stats', filters],
    queryFn: () => analyticsApi.getStats(filters),
    staleTime: 60_000,
  })
}

export function useAnalyticsDailyActivity(filters: AnalyticsFilters) {
  return useQuery({
    queryKey: ['analytics', 'daily', filters],
    queryFn: () => analyticsApi.getDailyActivity(filters),
    staleTime: 60_000,
  })
}
