import type { QueryClient } from '@tanstack/react-query'
import { wsManager } from '@/api/websocket'
import { native } from '@/services/native'

/**
 * Регистрирует обработчики WebSocket-событий.
 * Вызывается один раз при монтировании AppLayout.
 * Возвращает функцию cleanup для отписки.
 */
export function initWebSocketHandlers(queryClient: QueryClient): () => void {
  const unsubNewCandidate = wsManager.on('new_candidate', () => {
    void queryClient.invalidateQueries({ queryKey: ['candidates'] })
  })

  const unsubNewMessage = wsManager.on('new_message', async (msg) => {
    void queryClient.invalidateQueries({ queryKey: ['chats'] })
    void queryClient.invalidateQueries({ queryKey: ['chat', msg.chat_id] })
    await native.notify('Новое сообщение', String(msg.preview ?? ''))
  })

  const unsubMailingProgress = wsManager.on('mailing_progress', (msg) => {
    queryClient.setQueryData(
      ['mailing', msg.job_id],
      (old: Record<string, unknown> | undefined) => {
        if (!old) return old
        return { ...old, ...msg }
      }
    )
  })

  const unsubOrgAccess = wsManager.on('org_access_changed', (msg) => {
    if (msg.status !== 'active') {
      window.location.href = '/login'
    }
  })

  return () => {
    unsubNewCandidate()
    unsubNewMessage()
    unsubMailingProgress()
    unsubOrgAccess()
  }
}
