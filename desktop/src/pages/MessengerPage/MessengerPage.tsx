import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ShieldOff, ArrowLeft } from 'lucide-react'
import { useChatList, useChatMessages, useSendMessage, chatKeys } from '@/hooks/useChats'
import { useDebounce } from '@/hooks/useDebounce'
import { chatApi } from '@/api/chat'
import { ChatList } from '@/components/chat/ChatList'
import { MessagesList } from '@/components/chat/MessagesList'
import { MessageInput } from '@/components/chat/MessageInput'
import { EmptyState } from '@/components/ui/EmptyState'
import { useUIStore } from '@/stores/ui.store'
import { wsManager } from '@/api/websocket'
import { useQueryClient, useQuery } from '@tanstack/react-query'
import { avitoAccountsApi } from '@/api/avito-accounts'
import type { ChatListItem, Message } from '@/types/chat'

const LS_FILTERS_OPEN = 'mp_filters_open'

export default function MessengerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const showToast = useUIStore(s => s.showToast)
  const qc = useQueryClient()

  const [search, setSearch] = useState(() => searchParams.get('search') ?? '')
  const [onlyUnread, setOnlyUnread] = useState(() => searchParams.get('only_unread') === 'true')
  const [avitoAccountId, setAvitoAccountId] = useState(() => searchParams.get('avito_account_id') ?? '')
  const [filtersOpen, setFiltersOpen] = useState(() => {
    const stored = localStorage.getItem(LS_FILTERS_OPEN)
    return stored !== null ? stored === 'true' : false
  })
  const [selectedChat, setSelectedChat] = useState<ChatListItem | null>(null)

  const debouncedSearch = useDebounce(search, 300)

  // Синхронизация фильтров в URL (сохраняем candidate_id если есть)
  useEffect(() => {
    setSearchParams(prev => {
      const p = new URLSearchParams()
      const candidateId = prev.get('candidate_id')
      if (candidateId) p.set('candidate_id', candidateId)
      if (debouncedSearch) p.set('search', debouncedSearch)
      if (onlyUnread) p.set('only_unread', 'true')
      if (avitoAccountId) p.set('avito_account_id', avitoAccountId)
      return p
    }, { replace: true })
  }, [debouncedSearch, onlyUnread, avitoAccountId, setSearchParams])

  const handleToggleFilters = useCallback(() => {
    setFiltersOpen(prev => {
      const next = !prev
      localStorage.setItem(LS_FILTERS_OPEN, String(next))
      return next
    })
  }, [])

  const { data: chats = [], isLoading: chatsLoading } = useChatList({
    search: debouncedSearch || undefined,
    has_unread: onlyUnread || undefined,
    avito_account_id: avitoAccountId || undefined,
  })

  const { data: accounts = [] } = useQuery({
    queryKey: ['avito-accounts'],
    queryFn: () => avitoAccountsApi.getList(),
    staleTime: 60_000,
  })

  // Открыть чат по URL-параметру candidate_id
  useEffect(() => {
    const candidateId = searchParams.get('candidate_id')
    if (!candidateId || chats.length === 0) return
    const chat = chats.find(c => c.candidate_id === candidateId)
    if (chat) {
      setSelectedChat(chat)
      const p = new URLSearchParams(searchParams)
      p.delete('candidate_id')
      setSearchParams(p, { replace: true })
    }
  }, [searchParams, chats, setSearchParams])

  // Сообщения выбранного чата
  const chatId = selectedChat?.chat_id ?? ''
  const { data: messages = [], isLoading: messagesLoading } = useChatMessages(chatId)
  const sendMessage = useSendMessage(chatId)

  // WS: реалтайм новые сообщения
  useEffect(() => {
    const unsub = wsManager.on('new_message', (msg) => {
      const incomingChatId = String(msg.chat_id ?? '')
      if (!incomingChatId) return

      qc.setQueryData(
        chatKeys.messages(incomingChatId),
        (old: Message[] | undefined) => {
          if (!old) return old
          const newMsg = msg as unknown as Message
          if (old.some(m => m.id === newMsg.id)) return old
          return [...old, newMsg]
        }
      )

      void qc.invalidateQueries({ queryKey: chatKeys.all })
    })
    return unsub
  }, [qc])

  const handleSelectChat = useCallback(async (chat: ChatListItem) => {
    setSelectedChat(chat)
    try {
      await chatApi.markRead(chat.chat_id)
      void qc.invalidateQueries({ queryKey: chatKeys.all })
    } catch {
      // silent — не критично
    }
  }, [qc])

  const handleSend = useCallback(async (text: string) => {
    if (!chatId) return
    try {
      await sendMessage.mutateAsync(text)
    } catch {
      showToast('error', 'Не удалось отправить сообщение')
    }
  }, [chatId, sendMessage, showToast])

  const handleLoadMore = useCallback(() => {
    // Cursor pagination будет реализована с useInfiniteQuery при обновлении API
  }, [])

  const accountOptions = accounts.map(a => ({ id: a.id, name: a.name }))

  return (
    <div className="mp-page">
      <ChatList
        chats={chats}
        loading={chatsLoading}
        selectedId={selectedChat?.candidate_id ?? null}
        onSelect={chat => void handleSelectChat(chat)}
        search={search}
        onSearchChange={setSearch}
        onlyUnread={onlyUnread}
        onToggleUnread={setOnlyUnread}
        avitoAccountId={avitoAccountId}
        onAvitoAccountChange={setAvitoAccountId}
        accounts={accountOptions}
        filtersOpen={filtersOpen}
        onToggleFilters={handleToggleFilters}
      />

      <div className="mp-chat">
        {!selectedChat ? (
          <div className="mp-no-chat">
            <EmptyState
              title="Выберите чат"
              description="Выберите кандидата из списка слева, чтобы начать переписку"
            />
          </div>
        ) : (
          <>
            <div className="mp-chat-header">
              <button
                className="mp-back-btn"
                onClick={() => setSelectedChat(null)}
                aria-label="Назад"
              >
                <ArrowLeft size={18} />
              </button>
              <div className="mp-chat-info">
                <div className="mp-chat-name">{selectedChat.candidate_name ?? 'Неизвестный'}</div>
                {selectedChat.is_blocked && (
                  <div className="mp-chat-blocked-label">Заблокирован</div>
                )}
              </div>
              {selectedChat.is_blocked && (
                <div className="mp-blocked-badge">
                  <ShieldOff size={14} />
                  <span>Заблокирован</span>
                </div>
              )}
            </div>

            <MessagesList
              messages={messages}
              loading={messagesLoading}
              hasMore={false}
              onLoadMore={handleLoadMore}
            />

            <MessageInput
              onSend={text => void handleSend(text)}
              disabled={selectedChat.is_blocked}
              sending={sendMessage.isPending}
            />
          </>
        )}
      </div>

      <style>{`
        .mp-page {
          display: flex;
          height: 100%;
          overflow: hidden;
          background: var(--color-bg);
        }
        .mp-chat {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .mp-no-chat {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .mp-chat-header {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 14px 20px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          flex-shrink: 0;
        }
        .mp-back-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          transition: background 0.15s;
        }
        .mp-back-btn:hover { background: var(--color-bg); color: var(--color-text); }
        .mp-chat-info { flex: 1; }
        .mp-chat-name { font-size: 16px; font-weight: 600; }
        .mp-chat-blocked-label { font-size: 12px; color: var(--color-danger); margin-top: 2px; }
        .mp-blocked-badge {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px 10px;
          background: #fee2e2;
          color: var(--color-danger);
          border-radius: 999px;
          font-size: 12px;
          font-weight: 500;
        }
      `}</style>
    </div>
  )
}
