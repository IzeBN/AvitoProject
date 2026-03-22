import { Search, SlidersHorizontal } from 'lucide-react'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import type { ChatListItem } from '@/types/chat'

interface ChatListProps {
  chats: ChatListItem[]
  loading: boolean
  selectedId: string | null
  onSelect: (chat: ChatListItem) => void
  search: string
  onSearchChange: (v: string) => void
  onlyUnread: boolean
  onToggleUnread: (v: boolean) => void
  avitoAccountId: string
  onAvitoAccountChange: (v: string) => void
  accounts: Array<{ id: string; name: string }>
  stageId: string
  onStageChange: (v: string) => void
  stages: Array<{ id: string; name: string; color: string | null }>
  responsibleId: string
  onResponsibleChange: (v: string) => void
  responsibles: Array<{ id: string; full_name: string }>
  filtersOpen: boolean
  onToggleFilters: () => void
}

const formatLastMessage = (msg: string | null): string => {
  if (!msg) return 'Нет сообщений'
  if (msg.startsWith('http') && (msg.includes('avito.ru') || msg.includes('.jpg') || msg.includes('.png') || msg.includes('.jpeg') || msg.includes('.webp'))) {
    return '📷 Фото'
  }
  return msg
}

const formatLastTime = (iso: string | null) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

export const ChatList = ({
  chats,
  loading,
  selectedId,
  onSelect,
  search,
  onSearchChange,
  onlyUnread,
  onToggleUnread,
  avitoAccountId,
  onAvitoAccountChange,
  accounts,
  stageId,
  onStageChange,
  stages,
  responsibleId,
  onResponsibleChange,
  responsibles,
  filtersOpen,
  onToggleFilters,
}: ChatListProps) => {
  return (
    <div className="clist">
      {/* Шапка с кнопкой фильтров */}
      <div className="clist-header">
        <span className="clist-header-title">Чаты</span>
        <button
          className={`clist-filter-btn ${filtersOpen ? 'clist-filter-btn--active' : ''}`}
          onClick={onToggleFilters}
          aria-label="Фильтры"
          title="Фильтры"
        >
          <SlidersHorizontal size={15} />
        </button>
      </div>

      {/* Фильтры (сворачиваемые) */}
      {filtersOpen && (
        <div className="clist-search-wrap">
          <div className="clist-search-row">
            <Search size={14} className="clist-search-icon" />
            <input
              type="text"
              className="clist-search"
              placeholder="Поиск чатов..."
              value={search}
              onChange={e => onSearchChange(e.target.value)}
              aria-label="Поиск по чатам"
            />
          </div>
          <label className="clist-unread-toggle">
            <input
              type="checkbox"
              checked={onlyUnread}
              onChange={e => onToggleUnread(e.target.checked)}
            />
            <span>Только непрочитанные</span>
          </label>
          {accounts.length > 0 && (
            <select
              className="clist-account-select"
              value={avitoAccountId}
              onChange={e => onAvitoAccountChange(e.target.value)}
              aria-label="Аккаунт Авито"
            >
              <option value="">Все аккаунты</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          )}
          {stages.length > 0 && (
            <select
              className="clist-account-select"
              value={stageId}
              onChange={e => onStageChange(e.target.value)}
              aria-label="Этап"
            >
              <option value="">Все этапы</option>
              {stages.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
          {responsibles.length > 0 && (
            <select
              className="clist-account-select"
              value={responsibleId}
              onChange={e => onResponsibleChange(e.target.value)}
              aria-label="Ответственный"
            >
              <option value="">Все ответственные</option>
              {responsibles.map(r => (
                <option key={r.id} value={r.id}>{r.full_name}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {/* Список */}
      <div className="clist-items" role="listbox" aria-label="Список чатов">
        {loading ? (
          <div className="clist-loading"><Spinner size="md" /></div>
        ) : chats.length === 0 ? (
          <EmptyState
            title={onlyUnread ? 'Нет непрочитанных' : 'Нет чатов'}
            description={search ? 'Попробуйте другой запрос' : undefined}
          />
        ) : (
          chats.map(chat => {
            const isSelected = chat.candidate_id === selectedId
            return (
              <button
                key={chat.candidate_id}
                className={`clist-item ${isSelected ? 'clist-item--active' : ''} ${chat.unread_count > 0 ? 'clist-item--unread' : ''}`}
                onClick={() => onSelect(chat)}
                role="option"
                aria-selected={isSelected}
              >
                <div className="clist-avatar">
                  {(chat.candidate_name?.[0] ?? '?').toUpperCase()}
                  {chat.unread_count > 0 && (
                    <span className="clist-unread-dot" />
                  )}
                </div>
                <div className="clist-item-body">
                  <div className="clist-item-top">
                    <span className="clist-item-name">
                      {chat.candidate_name ?? 'Неизвестный'}
                    </span>
                    <span className="clist-item-time">
                      {formatLastTime(chat.last_message_at)}
                    </span>
                  </div>
                  <div className="clist-item-bottom">
                    <span className="clist-item-preview">
                      {formatLastMessage(chat.last_message)}
                    </span>
                    {chat.unread_count > 0 && (
                      <span className="clist-badge">{chat.unread_count}</span>
                    )}
                  </div>
                </div>
              </button>
            )
          })
        )}
      </div>

      <style>{`
        .clist {
          width: 280px;
          border-right: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          background: var(--color-surface);
          flex-shrink: 0;
        }
        .clist-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 12px 10px;
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .clist-header-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--color-text);
        }
        .clist-filter-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          transition: background 0.15s, color 0.15s;
        }
        .clist-filter-btn:hover { background: var(--color-bg); color: var(--color-text); }
        .clist-filter-btn--active { background: #eff6ff; color: var(--color-primary); }
        .clist-search-wrap {
          padding: 10px 12px;
          border-bottom: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          gap: 8px;
          flex-shrink: 0;
        }
        .clist-search-row {
          position: relative;
          display: flex;
          align-items: center;
        }
        .clist-search-icon {
          position: absolute;
          left: 10px;
          color: var(--color-text-secondary);
          pointer-events: none;
        }
        .clist-search {
          width: 100%;
          padding: 7px 10px 7px 32px;
          font-size: 13px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-bg);
          color: var(--color-text);
          outline: none;
          transition: border-color 0.15s;
        }
        .clist-search:focus { border-color: var(--color-primary); }
        .clist-search::placeholder { color: var(--color-text-secondary); }
        .clist-unread-toggle {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: var(--color-text-secondary);
          cursor: pointer;
        }
        .clist-account-select {
          width: 100%;
          padding: 6px 10px;
          font-size: 12px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-bg);
          color: var(--color-text);
          outline: none;
        }
        .clist-account-select:focus { border-color: var(--color-primary); }
        .clist-items {
          flex: 1;
          overflow-y: auto;
        }
        .clist-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 32px;
        }
        .clist-item {
          width: 100%;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          cursor: pointer;
          border-bottom: 1px solid var(--color-border);
          transition: background 0.1s;
          text-align: left;
        }
        .clist-item:hover { background: var(--color-bg); }
        .clist-item--active { background: #eff6ff; }
        .clist-item--active:hover { background: #dbeafe; }
        .clist-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--color-primary);
          color: #fff;
          font-size: 16px;
          font-weight: 600;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          position: relative;
        }
        .clist-unread-dot {
          position: absolute;
          top: 0;
          right: 0;
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: var(--color-danger);
          border: 2px solid var(--color-surface);
        }
        .clist-item-body { flex: 1; min-width: 0; }
        .clist-item-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 4px;
          margin-bottom: 3px;
        }
        .clist-item-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .clist-item--unread .clist-item-name { font-weight: 600; }
        .clist-item-time {
          font-size: 11px;
          color: var(--color-text-secondary);
          flex-shrink: 0;
        }
        .clist-item-bottom {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 4px;
        }
        .clist-item-preview {
          font-size: 12px;
          color: var(--color-text-secondary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex: 1;
        }
        .clist-item--unread .clist-item-preview { color: var(--color-text); }
        .clist-badge {
          background: var(--color-danger);
          color: #fff;
          font-size: 11px;
          font-weight: 600;
          min-width: 18px;
          height: 18px;
          border-radius: 999px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 5px;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  )
}
