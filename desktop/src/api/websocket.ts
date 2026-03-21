import { useAuthStore } from '@/stores/auth.store'

type WSMessage = { type: string; [key: string]: unknown }
type Handler = (msg: WSMessage) => void
type Unsubscribe = () => void

class WebSocketManager {
  private ws: WebSocket | null = null
  private handlers = new Map<string, Set<Handler>>()
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = true

  connect(): void {
    const token = useAuthStore.getState().accessToken
    if (!token) return

    const base = (
      import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
    ).replace(/^http/, 'ws')

    this.ws = new WebSocket(`${base}/ws?token=${token}`)

    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string) as WSMessage
        this.handlers.get(msg.type)?.forEach(h => h(msg))
        this.handlers.get('*')?.forEach(h => h(msg))
      } catch {
        // Игнорируем невалидные сообщения
      }
    }

    this.ws.onclose = () => {
      this.clearTimers()
      if (this.shouldReconnect) {
        this.reconnectTimeout = setTimeout(() => this.connect(), 3_000)
      }
    }

    this.ws.onopen = () => {
      this.pingInterval = setInterval(() => {
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30_000)
    }
  }

  /**
   * Подписывается на тип события. Возвращает функцию отписки.
   * Используйте '*' чтобы слушать все события.
   */
  on(type: string, handler: Handler): Unsubscribe {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
    return () => this.handlers.get(type)?.delete(handler)
  }

  disconnect(): void {
    this.shouldReconnect = false
    this.clearTimers()
    this.ws?.close()
    this.ws = null
  }

  private clearTimers(): void {
    if (this.pingInterval !== null) clearInterval(this.pingInterval)
    if (this.reconnectTimeout !== null) clearTimeout(this.reconnectTimeout)
    this.pingInterval = null
    this.reconnectTimeout = null
  }
}

export const wsManager = new WebSocketManager()
