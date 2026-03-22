import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tasksApi, type TaskCreatePayload } from '@/api/tasks'

const TASKS_KEY = ['tasks'] as const

export function useTasks(params?: { status?: string; assignee_id?: string }) {
  return useQuery({
    queryKey: [...TASKS_KEY, params],
    queryFn: () => tasksApi.getList(params),
    staleTime: 5_000,
    refetchInterval: 10_000,
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TaskCreatePayload) => tasksApi.create(data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: TASKS_KEY }),
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<TaskCreatePayload> }) =>
      tasksApi.update(id, data),
    onSuccess: () => void qc.invalidateQueries({ queryKey: TASKS_KEY }),
  })
}
