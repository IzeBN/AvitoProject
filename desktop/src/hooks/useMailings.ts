import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { mailingsApi } from '@/api/mailings'

export const mailingKeys = {
  all: ['mailings'] as const,
  detail: (id: string) => ['mailing', id] as const,
}

const ACTIVE_STATUSES = new Set(['running', 'pending', 'pausing'])

export function useMailings() {
  return useQuery({
    queryKey: mailingKeys.all,
    queryFn: () => mailingsApi.getList(),
    staleTime: 2_000,
    refetchInterval: (query) => {
      const items = query.state.data as { status: string }[] | undefined
      const hasActive = items?.some(m => ACTIVE_STATUSES.has(m.status))
      return hasActive ? 3_000 : 30_000
    },
  })
}

export function useStartMailing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: mailingsApi.start,
    onSuccess: () => void qc.invalidateQueries({ queryKey: mailingKeys.all }),
  })
}

export function usePauseMailing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => mailingsApi.pause(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: mailingKeys.all }),
  })
}

export function useCancelMailing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => mailingsApi.cancel(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: mailingKeys.all }),
  })
}

export function useResumeMailing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => mailingsApi.resume(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: mailingKeys.all }),
  })
}
