import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useParams, useNavigate } from 'react-router-dom'
import { ShieldOff, ArrowLeft, RefreshCw, User, X } from 'lucide-react'
import { useChatList, useChatMessages, useSendMessage, chatKeys } from '@/hooks/useChats'
import { useCandidate } from '@/hooks/useCandidates'
import { useDebounce } from '@/hooks/useDebounce'
import { chatApi } from '@/api/chat'
import { ChatList } from '@/components/chat/ChatList'
import { MessagesList } from '@/components/chat/MessagesList'
import { MessageInput } from '@/components/chat/MessageInput'
import { EmptyState } from '@/components/ui/EmptyState'
import { useUIStore } from '@/stores/ui.store'
import { wsManager } from '@/api/websocket'
import { useQueryClient, useQuery, useMutation } from '@tanstack/react-query'
import type { ChatListItem, Message } from '@/types/chat'

const LS_FILTERS_OPEN = 'mp_filters_open'

// ─── Candidate panel ────────────────────────────────────────────────────────

interface CandidatePanelProps {
  candidateId: string
  onClose: () => void
  onNavigate: (id: string) => void
}

const CandidatePanel = ({ candidateId, onClose, onNavigate }: CandidatePanelProps) => {
  const { data: candidate, isLoading } = useCandidate(candidateId)

  return (
    <div className="mp-cpanel">
      <div className="mp-cpanel-header">
        <span className="mp-cpanel-title">
          {isLoading ? 'Загрузка...' : (candidate?.name ?? 'Кандидат')}
        </span>
        <button onClick={onClose} aria-label="Закрыть панель">
          <X size={18} />
        </button>
      </div>

      {!isLoading && candidate && (
        <div className="mp-cpanel-body">
          <div className="mp-cpanel-field">
            <span className="mp-cpanel-label">Телефон</span>
            <span className="mp-cpanel-value">{candidate.phone ?? '—'}</span>
          </div>

          {candidate.location && (
            <div className="mp-cpanel-field">
              <span className="mp-cpanel-label">Город / Локация</span>
              <span className="mp-cpanel-value">{candidate.location}</span>
            </div>
          )}

          <div className="mp-cpanel-field">
            <span className="mp-cpanel-label">Вакансия</span>
            <span className="mp-cpanel-value">{candidate.vacancy ?? '—'}</span>
          </div>

          <div className="mp-cpanel-field">
            <span className="mp-cpanel-label">Этап</span>
            <span className="mp-cpanel-value">{candidate.stage?.name ?? '—'}</span>
          </div>

          <div className="mp-cpanel-field">
            <span className="mp-cpanel-label">Отдел</span>
            <span className="mp-cpanel-value">{candidate.department?.name ?? '—'}</span>
          </div>

          <div className="mp-cpanel-field">
            <span className="mp-cpanel-label">Ответственный</span>
            <span className="mp-cpanel-value">{candidate.responsible?.full_name ?? '—'}</span>
          </div>

          {candidate.tags.length > 0 && (
            <div className="mp-cpanel-field">
              <span className="mp-cpanel-label">Теги</span>
              <div className="mp-cpanel-tags">
                {candidate.tags.map(tag => (
                  <span key={tag.id} className="mp-cpanel-tag">{tag.name}</span>
                ))}
              </div>
            </div>
          )}

          {candidate.comment && (
            <div className="mp-cpanel-field">
              <span className="mp-cpanel-label">Комментарий</span>
              <span className="mp-cpanel-value">{candidate.comment}</span>
            </div>
          )}

          {candidate.source && (
            <div className="mp-cpanel-field">
              <span className="mp-cpanel-label">Источник</span>
              <span className="mp-cpanel-value">{candidate.source}</span>
            </div>
          )}

          <div className="mp-cpanel-field">
            <span className="mp-cpanel-label">Добавлен</span>
            <span className="mp-cpanel-value">
              {new Date(candidate.created_at).toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: 'long',
                year: 'numeric',
              })}
            </span>
          </div>

          <div style={{ paddingTop: 12 }}>
            <button
              className="mp-card-btn"
              onClick={() => onNavigate(candidateId)}
              style={{ width: '100%', justifyContent: 'center', fontSize: 13 }}
            >
              Изменить
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────────────

export default function MessengerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { candidateId: urlCandidateId } = useParams<{ candidateId?: string }>()
  const navigate = useNavigate()
  const showToast = useUIStore(s => s.showToast)
  const qc = useQueryClient()

  const [search, setSearch] = useState(() => searchParams.get('search') ?? '')
  const [onlyUnread, setOnlyUnread] = useState(() => searchParams.get('only_unread') === 'true')
  const [avitoAccountId, setAvitoAccountId] = useState(() => searchParams.get('avito_account_id') ?? '')
  const [stageId, setStageId] = useState(() => searchParams.get('stage_id') ?? '')
  const [responsibleId, setResponsibleId] = useState(() => searchParams.get('responsible_id') ?? '')
  const [candidatePanelOpen, setCandidatePanelOpen] = useState(false)

  const [filtersOpen, setFiltersOpen] = useState(() => {
    const stored = localStorage.getItem(LS_FILTERS_OPEN)
    return stored !== null ? stored === 'true' : false
  })

  const debouncedSearch = useDebounce(search, 300)

  // Синхронизация фильтров в URL
  useEffect(() => {
    setSearchParams(prev => {
      const p = new URLSearchParams()
      if (debouncedSearch) p.set('search', debouncedSearch)
      if (onlyUnread) p.set('only_unread', 'true')
      if (avitoAccountId) p.set('avito_account_id', avitoAccountId)
      if (stageId) p.set('stage_id', stageId)
      if (responsibleId) p.set('responsible_id', responsibleId)
      return p
    }, { replace: true })
  }, [debouncedSearch, onlyUnread, avitoAccountId, stageId, responsibleId, setSearchParams])

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
    stage_id: stageId || undefined,
    responsible_id: responsibleId || undefined,
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['chat-filters'],
    queryFn: () => chatApi.getFilters(),
    staleTime: 120_000,
  })

  // Derive selected chat from URL param
  const selectedChat: ChatListItem | null = urlCandidateId
    ? (chats.find(c => c.candidate_id === urlCandidateId) ?? null)
    : null

  // Сообщения выбранного чата
  const candidateId = urlCandidateId ?? ''
  const { data: messages = [], isLoading: messagesLoading } = useChatMessages(candidateId)
  const sendMessage = useSendMessage(candidateId)

  const syncMutation = useMutation({
    mutationFn: () => chatApi.syncChat(candidateId),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: chatKeys.messages(candidateId) })
      showToast('success', `Синхронизировано: +${data.added} сообщений`)
    },
    onError: () => showToast('error', 'Не удалось синхронизировать'),
  })

  // WS: реалтайм новые сообщения
  useEffect(() => {
    const unsubMsg = wsManager.on('new_message', (msg) => {
      const incomingCandidateId = String(msg.candidate_id ?? '')
      if (!incomingCandidateId) return

      qc.setQueryData(
        chatKeys.messages(incomingCandidateId),
        (old: Message[] | undefined) => {
          if (!old) return old
          const newMsg = msg as unknown as Message
          if (old.some(m => m.id === newMsg.id)) return old
          return [...old, newMsg]
        }
      )

      void qc.invalidateQueries({ queryKey: chatKeys.all })
    })

    // WS: новый кандидат/отклик — обновляем список чатов
    const unsubCandidate = wsManager.on('new_candidate', () => {
      void qc.invalidateQueries({ queryKey: chatKeys.all })
    })

    return () => {
      unsubMsg()
      unsubCandidate()
    }
  }, [qc])

  const handleSelectChat = useCallback(async (chat: ChatListItem) => {
    const params = new URLSearchParams()
    if (debouncedSearch) params.set('search', debouncedSearch)
    if (onlyUnread) params.set('only_unread', 'true')
    if (avitoAccountId) params.set('avito_account_id', avitoAccountId)
    const qs = params.toString()
    navigate(`/messenger/${chat.candidate_id}${qs ? '?' + qs : ''}`)
    try {
      await chatApi.markRead(chat.candidate_id)
      void qc.invalidateQueries({ queryKey: chatKeys.all })
    } catch { /* silent */ }
  }, [navigate, debouncedSearch, onlyUnread, avitoAccountId, qc])

  const handleBack = useCallback(() => {
    const params = new URLSearchParams()
    if (debouncedSearch) params.set('search', debouncedSearch)
    if (onlyUnread) params.set('only_unread', 'true')
    if (avitoAccountId) params.set('avito_account_id', avitoAccountId)
    const qs = params.toString()
    navigate(`/messenger${qs ? '?' + qs : ''}`)
  }, [navigate, debouncedSearch, onlyUnread, avitoAccountId])

  const handleSend = useCallback(async (text: string) => {
    if (!candidateId) return
    try {
      await sendMessage.mutateAsync(text)
    } catch {
      showToast('error', 'Не удалось отправить сообщение')
    }
  }, [candidateId, sendMessage, showToast])

  const handleLoadMore = useCallback(() => {
    // Cursor pagination будет реализована с useInfiniteQuery при обновлении API
  }, [])

  return (
    <div className="mp-page">
      <ChatList
        chats={chats}
        loading={chatsLoading}
        selectedId={urlCandidateId ?? null}
        onSelect={chat => void handleSelectChat(chat)}
        search={search}
        onSearchChange={setSearch}
        onlyUnread={onlyUnread}
        onToggleUnread={setOnlyUnread}
        avitoAccountId={avitoAccountId}
        onAvitoAccountChange={setAvitoAccountId}
        accounts={filterOptions?.avito_accounts ?? []}
        stageId={stageId}
        onStageChange={setStageId}
        stages={filterOptions?.stages ?? []}
        responsibleId={responsibleId}
        onResponsibleChange={setResponsibleId}
        responsibles={filterOptions?.responsible_users ?? []}
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
            <div className="mp-chat-main">
              <div className="mp-chat-header">
                <button
                  className="mp-back-btn"
                  onClick={handleBack}
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
                <button
                  className={`mp-sync-btn${syncMutation.isPending ? ' mp-sync-btn--spinning' : ''}`}
                  onClick={() => void syncMutation.mutate()}
                  disabled={syncMutation.isPending}
                  aria-label="Синхронизировать сообщения"
                  title="Загрузить историю сообщений из Avito"
                >
                  <RefreshCw size={16} />
                </button>
                <button
                  className={`mp-card-btn${candidatePanelOpen ? ' mp-card-btn--active' : ''}`}
                  onClick={() => setCandidatePanelOpen(prev => !prev)}
                  aria-label="Карточка кандидата"
                  title="Карточка кандидата"
                >
                  <User size={16} />
                  <span>Карточка</span>
                </button>
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
            </div>

            {candidatePanelOpen && candidateId && (
              <CandidatePanel
                candidateId={candidateId}
                onClose={() => setCandidatePanelOpen(false)}
                onNavigate={(id) => navigate(`/candidates?open=${id}`)}
              />
            )}
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
          flex-direction: row;
          overflow: hidden;
        }
        .mp-chat-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-width: 0;
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
        .mp-sync-btn {
          display: flex; align-items: center; justify-content: center;
          width: 32px; height: 32px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          transition: background 0.15s, color 0.15s;
          flex-shrink: 0;
        }
        .mp-sync-btn:hover:not(:disabled) { background: var(--color-bg); color: var(--color-text); }
        .mp-sync-btn:disabled { opacity: 0.5; }
        .mp-sync-btn--spinning svg { animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .mp-card-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          height: 32px;
          padding: 0 10px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          font-size: 13px;
          font-weight: 500;
          transition: background 0.15s, color 0.15s;
          flex-shrink: 0;
        }
        .mp-card-btn:hover { background: var(--color-bg); color: var(--color-text); }
        .mp-card-btn--active { background: var(--color-bg); color: var(--color-primary); }
        .mp-cpanel {
          width: 340px;
          flex-shrink: 0;
          border-left: 1px solid var(--color-border);
          background: var(--color-surface);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .mp-cpanel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 16px;
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .mp-cpanel-header button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          transition: background 0.15s;
          flex-shrink: 0;
        }
        .mp-cpanel-header button:hover { background: var(--color-bg); color: var(--color-text); }
        .mp-cpanel-title {
          font-size: 15px;
          font-weight: 600;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .mp-cpanel-body {
          flex: 1;
          overflow-y: auto;
          padding: 12px 16px;
          display: flex;
          flex-direction: column;
          gap: 0;
        }
        .mp-cpanel-field {
          display: flex;
          flex-direction: column;
          gap: 3px;
          padding: 10px 0;
          border-bottom: 1px solid var(--color-border);
        }
        .mp-cpanel-field:last-child { border-bottom: none; }
        .mp-cpanel-label {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-secondary);
        }
        .mp-cpanel-value { font-size: 13px; color: var(--color-text); }
        .mp-cpanel-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          margin-top: 2px;
        }
        .mp-cpanel-tag {
          padding: 2px 8px;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 500;
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          color: var(--color-text);
        }
      `}</style>
    </div>
  )
}
