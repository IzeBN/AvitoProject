import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { mailingsApi } from '@/api/mailings'

export const mailingKeys = {
  all: ['mailings'] as const,
  detail: (id: string) => ['mailing', id] as const,
}

export function useMailings() {
  return useQuery({
    queryKey: mailingKeys.all,
    queryFn: () => mailingsApi.getList(),
    staleTime: 10_000,
    refetchInterval: 15_000,
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
