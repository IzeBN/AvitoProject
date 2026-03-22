import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { vacanciesApi, type Vacancy } from '@/api/vacancies'

const VACANCIES_KEY = ['vacancies'] as const

export function useVacancies() {
  return useQuery({
    queryKey: VACANCIES_KEY,
    queryFn: () => vacanciesApi.getList(),
    staleTime: 5_000,
    refetchInterval: 10_000,
  })
}

export function useCreateVacancy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Omit<Vacancy, 'id' | 'created_at'>) =>
      vacanciesApi.create(data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: VACANCIES_KEY }),
  })
}

export function useUpdateVacancy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Vacancy> }) =>
      vacanciesApi.update(id, data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: VACANCIES_KEY }),
  })
}
