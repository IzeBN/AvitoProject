import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/api/chat'

export const chatKeys = {
  all: ['chats'] as const,
  list: (params?: { search?: string; has_unread?: boolean; avito_account_id?: string }) =>
    ['chats', 'list', params] as const,
  messages: (chatId: string) => ['chat', chatId, 'messages'] as const,
}

export function useChatList(params?: { search?: string; has_unread?: boolean; avito_account_id?: string }) {
  return useQuery({
    queryKey: chatKeys.list(params),
    queryFn: () => chatApi.getList(params),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })
}

export function useChatMessages(chatId: string) {
  return useQuery({
    queryKey: chatKeys.messages(chatId),
    queryFn: () => chatApi.getMessages(chatId),
    staleTime: 5_000,
    enabled: !!chatId,
  })
}

export function useSendMessage(chatId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) => chatApi.sendMessage(chatId, content),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: chatKeys.messages(chatId) })
      void qc.invalidateQueries({ queryKey: chatKeys.all })
    },
  })
}
