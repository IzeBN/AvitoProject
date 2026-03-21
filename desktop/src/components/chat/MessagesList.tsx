import { useEffect, useRef, useState, useCallback } from 'react'
import { MessageItem } from './MessageItem'
import { Spinner } from '@/components/ui/Spinner'
import type { Message } from '@/types/chat'

interface MessagesListProps {
  messages: Message[]
  loading: boolean
  hasMore: boolean
  onLoadMore: () => void
  loadingMore?: boolean
}

const isSameDay = (a: string, b: string) => {
  const da = new Date(a)
  const db = new Date(b)
  return da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
}

const formatDayLabel = (iso: string) => {
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  if (isSameDay(iso, today.toISOString())) return 'Сегодня'
  if (isSameDay(iso, yesterday.toISOString())) return 'Вчера'
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export const MessagesList = ({
  messages,
  loading,
  hasMore,
  onLoadMore,
  loadingMore = false,
}: MessagesListProps) => {
  const bottomRef = useRef<HTMLDivElement>(null)
  const topRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const prevLengthRef = useRef(messages.length)

  // Автоскролл вниз при новых сообщениях
  useEffect(() => {
    if (autoScroll && messages.length > prevLengthRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    prevLengthRef.current = messages.length
  }, [messages.length, autoScroll])

  // Бесконечная прокрутка вверх — IntersectionObserver на верхний sentinel
  useEffect(() => {
    const top = topRef.current
    if (!top || !hasMore || loadingMore) return

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) onLoadMore()
      },
      { threshold: 0.1, root: containerRef.current }
    )
    observer.observe(top)
    return () => observer.disconnect()
  }, [hasMore, loadingMore, onLoadMore])

  const handleScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    setAutoScroll(nearBottom)
  }, [])

  if (loading) {
    return (
      <div className="mlist-loading">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="mlist"
      onScroll={handleScroll}
      role="log"
      aria-label="История сообщений"
      aria-live="polite"
    >
      {/* Sentinel для загрузки предыдущих сообщений */}
      <div ref={topRef} className="mlist-sentinel" />

      {loadingMore && (
        <div className="mlist-more-loading">
          <Spinner size="sm" />
        </div>
      )}

      {messages.length === 0 ? (
        <div className="mlist-empty">
          <p>Нет сообщений. Начните диалог!</p>
        </div>
      ) : (
        messages.map((msg, idx) => {
          const prev = messages[idx - 1]
          const showDateSep = !prev || !isSameDay(prev.created_at, msg.created_at)
          return (
            <div key={msg.id}>
              {showDateSep && (
                <div className="mlist-date-sep">
                  <span>{formatDayLabel(msg.created_at)}</span>
                </div>
              )}
              <MessageItem message={msg} />
            </div>
          )
        })
      )}

      <div ref={bottomRef} />

      <style>{`
        .mlist {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 2px;
          padding: 12px 0;
          background: var(--color-bg);
          scroll-behavior: smooth;
        }
        .mlist-sentinel { height: 1px; }
        .mlist-loading, .mlist-empty {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px;
          color: var(--color-text-secondary);
          font-size: 14px;
        }
        .mlist-more-loading {
          display: flex;
          justify-content: center;
          padding: 8px;
        }
        .mlist-date-sep {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 12px 16px 8px;
        }
        .mlist-date-sep span {
          display: inline-block;
          padding: 4px 12px;
          background: rgba(0,0,0,.06);
          border-radius: 999px;
          font-size: 12px;
          color: var(--color-text-secondary);
        }
      `}</style>
    </div>
  )
}
