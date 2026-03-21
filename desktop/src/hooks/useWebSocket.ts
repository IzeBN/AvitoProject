import { useEffect } from 'react'
import { wsManager } from '@/api/websocket'

type WSMessage = { type: string; [key: string]: unknown }

/**
 * Подписывается на WebSocket-событие, автоматически отписывается при unmount.
 */
export function useWebSocketEvent(
  type: string,
  handler: (msg: WSMessage) => void
) {
  useEffect(() => {
    const unsub = wsManager.on(type, handler)
    return unsub
  }, [type, handler])
}
