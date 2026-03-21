import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { candidatesApi } from '@/api/candidates'
import type { CandidateFilters } from '@/types/candidate'

export const candidateKeys = {
  all: ['candidates'] as const,
  list: (filters: CandidateFilters, page: number) =>
    ['candidates', 'list', filters, page] as const,
  detail: (id: string) => ['candidates', 'detail', id] as const,
}

export function useCandidates(filters: CandidateFilters, page: number) {
  return useQuery({
    queryKey: candidateKeys.list(filters, page),
    queryFn: () => candidatesApi.getList(filters, page),
    placeholderData: prev => prev,
    staleTime: 15_000,
  })
}

export function useCandidate(id: string) {
  return useQuery({
    queryKey: candidateKeys.detail(id),
    queryFn: () => candidatesApi.getOne(id),
    staleTime: 30_000,
  })
}

export function useUpdateCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      candidatesApi.update(id, data),
    onSuccess: (_, { id }) => {
      void qc.invalidateQueries({ queryKey: candidateKeys.all })
      void qc.invalidateQueries({ queryKey: candidateKeys.detail(id) })
    },
  })
}

export function useBulkEditCandidates() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ ids, edit }: { ids: string[]; edit: Record<string, unknown> }) =>
      candidatesApi.bulkEdit(ids, edit),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: candidateKeys.all })
    },
  })
}
