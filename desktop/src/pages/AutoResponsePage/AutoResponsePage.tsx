import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  autoResponseApi,
  type AutoResponseRule,
  type FastAnswer,
  type DefaultMessage,
} from '@/api/auto-response'
import { avitoAccountsApi } from '@/api/avito-accounts'
import { Table, type Column } from '@/components/ui/Table'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { useUIStore } from '@/stores/ui.store'
import clsx from 'clsx'
import { Plus, Trash2, GripVertical } from 'lucide-react'

type Tab = 'rules' | 'default' | 'items' | 'fast'

const AUTO_TYPE_LABELS: Record<string, string> = {
  on_message: 'На сообщение',
  on_response: 'На отклик',
}




// ---- Debounced textarea для default messages ----
function DefaultMessageTextarea({
  accountId,
  initialMessage,
}: {
  accountId: string
  initialMessage: string
}) {
  const showToast = useUIStore(s => s.showToast)
  const [value, setValue] = useState(initialMessage)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const saveMutation = useMutation({
    mutationFn: (msg: string) => autoResponseApi.setDefaultMessage(accountId, msg),
    onError: () => showToast('error', 'Не удалось сохранить сообщение'),
  })

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      saveMutation.mutate(e.target.value)
    }, 1000)
  }

  return (
    <div style={{ position: 'relative' }}>
      <textarea
        value={value}
        onChange={handleChange}
        rows={3}
        style={{
          width: '100%',
          padding: '8px 12px',
          fontSize: 13,
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          background: 'var(--color-surface)',
          color: 'var(--color-text)',
          resize: 'vertical',
          outline: 'none',
          fontFamily: 'inherit',
        }}
      />
      {saveMutation.isPending && (
        <div style={{ position: 'absolute', right: 8, bottom: 8 }}>
          <Spinner size="sm" />
        </div>
      )}
    </div>
  )
}

// ---- Fast Answers with DnD ----
function FastAnswersTab() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingItem, setEditingItem] = useState<FastAnswer | null>(null)
  const [editText, setEditText] = useState('')
  const [newText, setNewText] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const [draggedId, setDraggedId] = useState<string | null>(null)
  const orderedRef = useRef<FastAnswer[]>([])

  const { data: answers, isLoading } = useQuery({
    queryKey: ['auto-response', 'fast-answers'],
    queryFn: () => autoResponseApi.getFastAnswers(),
    staleTime: 60_000,
  })

  const createMutation = useMutation({
    mutationFn: (msg: string) => autoResponseApi.createFastAnswer(msg),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['auto-response', 'fast-answers'] })
      showToast('success', 'Быстрый ответ добавлен')
      setShowAddModal(false)
      setNewText('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, msg }: { id: string; msg: string }) =>
      autoResponseApi.updateFastAnswer(id, msg),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['auto-response', 'fast-answers'] })
      setEditingItem(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => autoResponseApi.deleteFastAnswer(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['auto-response', 'fast-answers'] })
      setDeleteId(null)
    },
  })

  const reorderMutation = useMutation({
    mutationFn: (ids: string[]) => autoResponseApi.reorderFastAnswers(ids),
    onError: () => {
      void qc.invalidateQueries({ queryKey: ['auto-response', 'fast-answers'] })
      showToast('error', 'Не удалось сохранить порядок')
    },
  })

  const displayAnswers =
    orderedRef.current.length > 0 && draggedId ? orderedRef.current : (answers ?? [])

  const handleDragStart = (id: string) => {
    setDraggedId(id)
    orderedRef.current = [...(answers ?? [])]
  }

  const handleDragOver = (e: React.DragEvent, overId: string) => {
    e.preventDefault()
    if (overId === draggedId) return
    const current = [...orderedRef.current]
    const from = current.findIndex(a => a.id === draggedId)
    const to = current.findIndex(a => a.id === overId)
    if (from === -1 || to === -1) return
    const [item] = current.splice(from, 1)
    current.splice(to, 0, item)
    orderedRef.current = current
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const ids = orderedRef.current.map(a => a.id)
    qc.setQueryData<FastAnswer[]>(['auto-response', 'fast-answers'], orderedRef.current)
    reorderMutation.mutate(ids)
    setDraggedId(null)
    orderedRef.current = []
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
        <Spinner />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button icon={<Plus size={15} />} size="sm" onClick={() => setShowAddModal(true)}>
          Добавить
        </Button>
      </div>

      {!displayAnswers.length ? (
        <EmptyState title="Быстрых ответов нет" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }} onDrop={handleDrop} onDragOver={e => e.preventDefault()}>
          {displayAnswers.map(a => (
            <div
              key={a.id}
              draggable
              onDragStart={() => handleDragStart(a.id)}
              onDragOver={e => handleDragOver(e, a.id)}
              onDragEnd={() => { setDraggedId(null); orderedRef.current = [] }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                opacity: draggedId === a.id ? 0.4 : 1,
              }}
            >
              <span style={{ color: 'var(--color-text-secondary)', cursor: 'grab', display: 'flex' }}>
                <GripVertical size={16} />
              </span>
              <span
                style={{ flex: 1, fontSize: 13, cursor: 'pointer' }}
                onDoubleClick={() => {
                  setEditingItem(a)
                  setEditText(a.message)
                }}
                title="Двойной клик для редактирования"
              >
                {a.message}
              </span>
              <Button
                variant="ghost"
                size="sm"
                icon={<Trash2 size={13} />}
                onClick={() => setDeleteId(a.id)}
              />
            </div>
          ))}
        </div>
      )}

      <Modal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Новый быстрый ответ"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>Отмена</Button>
            <Button
              loading={createMutation.isPending}
              disabled={!newText.trim()}
              onClick={() => createMutation.mutate(newText.trim())}
            >
              Добавить
            </Button>
          </>
        }
      >
        <textarea
          autoFocus
          value={newText}
          onChange={e => setNewText(e.target.value)}
          rows={3}
          placeholder="Текст быстрого ответа..."
          style={{
            width: '100%',
            padding: '8px 12px',
            fontSize: 14,
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            resize: 'vertical',
            outline: 'none',
            fontFamily: 'inherit',
          }}
        />
      </Modal>

      <Modal
        open={editingItem !== null}
        onClose={() => setEditingItem(null)}
        title="Редактировать быстрый ответ"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditingItem(null)}>Отмена</Button>
            <Button
              loading={updateMutation.isPending}
              disabled={!editText.trim()}
              onClick={() => {
                if (editingItem) updateMutation.mutate({ id: editingItem.id, msg: editText.trim() })
              }}
            >
              Сохранить
            </Button>
          </>
        }
      >
        <textarea
          autoFocus
          value={editText}
          onChange={e => setEditText(e.target.value)}
          rows={3}
          style={{
            width: '100%',
            padding: '8px 12px',
            fontSize: 14,
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            resize: 'vertical',
            outline: 'none',
            fontFamily: 'inherit',
          }}
        />
      </Modal>

      <Modal
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        title="Удалить быстрый ответ?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteId(null)}>Отмена</Button>
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={() => { if (deleteId) deleteMutation.mutate(deleteId) }}
            >
              Удалить
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Быстрый ответ будет удалён навсегда.
        </p>
      </Modal>
    </div>
  )
}

// ---- Default messages tab ----
function DefaultMessagesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['auto-response', 'default-messages'],
    queryFn: () => autoResponseApi.getDefaultMessages(),
    staleTime: 60_000,
  })

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
  }

  if (!data?.length) {
    return <EmptyState title="Аккаунтов нет" description="Подключите Avito аккаунт для настройки сообщений" />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {data.map((item: DefaultMessage) => (
        <div key={item.avito_account_id}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>
            {item.avito_account_name ?? item.avito_account_id}
          </div>
          <DefaultMessageTextarea
            accountId={item.avito_account_id}
            initialMessage={item.message}
          />
        </div>
      ))}
    </div>
  )
}

// ---- Rules tab ----
function RulesTab() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newAccountId, setNewAccountId] = useState('')
  const [newItemId, setNewItemId] = useState('')
  const [newAutoType, setNewAutoType] = useState('on_message')
  const [deleteId, setDeleteId] = useState<string | null>(null)

  const { data: rules, isLoading } = useQuery({
    queryKey: ['auto-response', 'rules'],
    queryFn: () => autoResponseApi.getRules(),
    staleTime: 60_000,
  })

  const { data: accounts } = useQuery({
    queryKey: ['avito-accounts'],
    queryFn: () => avitoAccountsApi.getList(),
    staleTime: 120_000,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      autoResponseApi.createRule({
        avito_account_id: newAccountId,
        avito_item_id: newItemId ? parseInt(newItemId) : undefined,
        auto_type: newAutoType,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['auto-response', 'rules'] })
      showToast('success', 'Правило добавлено')
      setShowAddModal(false)
      setNewAccountId('')
      setNewItemId('')
    },
    onError: () => showToast('error', 'Не удалось создать правило'),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      autoResponseApi.updateRule(id, { is_active }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['auto-response', 'rules'] }),
    onError: () => showToast('error', 'Не удалось изменить статус'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => autoResponseApi.deleteRule(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['auto-response', 'rules'] })
      setDeleteId(null)
    },
    onError: () => showToast('error', 'Не удалось удалить правило'),
  })

  const columns: Column<AutoResponseRule>[] = [
    {
      key: 'account',
      title: 'Аккаунт',
      render: row => row.avito_account_name ?? row.avito_account_id,
    },
    {
      key: 'item',
      title: 'Объявление',
      render: row =>
        row.avito_item_id ? `#${row.avito_item_id}` : <Badge variant="info">Все объявления</Badge>,
    },
    {
      key: 'type',
      title: 'Тип',
      render: row =>
        row.auto_type ? (
          <Badge variant="default">{AUTO_TYPE_LABELS[row.auto_type] ?? row.auto_type}</Badge>
        ) : '—',
    },
    {
      key: 'active',
      title: 'Активно',
      align: 'center',
      render: row => (
        <input
          type="checkbox"
          checked={row.is_active}
          onChange={e => toggleMutation.mutate({ id: row.id, is_active: e.target.checked })}
          style={{ cursor: 'pointer', width: 16, height: 16, accentColor: 'var(--color-primary)' }}
        />
      ),
    },
    {
      key: 'actions',
      title: '',
      width: 48,
      align: 'center',
      render: row => (
        <Button
          variant="ghost"
          size="sm"
          icon={<Trash2 size={14} />}
          onClick={() => setDeleteId(row.id)}
        />
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button icon={<Plus size={15} />} size="sm" onClick={() => setShowAddModal(true)}>
          Добавить правило
        </Button>
      </div>

      <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <Table
          columns={columns}
          data={rules ?? []}
          rowKey={row => row.id}
          loading={isLoading}
          emptyText="Правил нет"
        />
      </div>

      <Modal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Новое правило автоответа"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>Отмена</Button>
            <Button
              loading={createMutation.isPending}
              disabled={!newAccountId}
              onClick={() => createMutation.mutate()}
            >
              Создать
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>
              Аккаунт *
            </label>
            <select
              value={newAccountId}
              onChange={e => setNewAccountId(e.target.value)}
              style={{ ...selectStyle, width: '100%' }}
            >
              <option value="">Выберите аккаунт</option>
              {accounts?.map(acc => (
                <option key={acc.id} value={acc.id}>{acc.name}</option>
              ))}
            </select>
          </div>
          <Input
            label="ID объявления (опционально)"
            placeholder="Оставьте пустым для всех объявлений"
            value={newItemId}
            onChange={e => setNewItemId(e.target.value)}
          />
          <div>
            <label style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>
              Тип автоответа
            </label>
            <select
              value={newAutoType}
              onChange={e => setNewAutoType(e.target.value)}
              style={{ ...selectStyle, width: '100%' }}
            >
              <option value="on_message">На входящее сообщение</option>
              <option value="on_response">На отклик</option>
            </select>
          </div>
        </div>
      </Modal>

      <Modal
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        title="Удалить правило?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteId(null)}>Отмена</Button>
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={() => { if (deleteId) deleteMutation.mutate(deleteId) }}
            >
              Удалить
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Правило автоответа будет удалено.
        </p>
      </Modal>
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '7px 12px',
  fontSize: 13,
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-sm)',
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  outline: 'none',
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'rules', label: 'Автоответы' },
  { id: 'default', label: 'Сообщения по умолчанию' },
  { id: 'fast', label: 'Быстрые ответы' },
]

export default function AutoResponsePage() {
  const [activeTab, setActiveTab] = useState<Tab>('rules')

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700 }}>Автоответы и сообщения</h1>

      <div style={{ display: 'flex', borderBottom: '1px solid var(--color-border)' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={clsx('ar-tab', activeTab === tab.id && 'ar-tab--active')}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'rules' && <RulesTab />}
      {activeTab === 'default' && <DefaultMessagesTab />}
      {activeTab === 'fast' && <FastAnswersTab />}

      <style>{`
        .ar-tab {
          padding: 10px 18px;
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text-secondary);
          border-bottom: 2px solid transparent;
          margin-bottom: -1px;
          transition: color 0.15s, border-color 0.15s;
        }
        .ar-tab:hover { color: var(--color-text); }
        .ar-tab--active {
          color: var(--color-primary);
          border-bottom-color: var(--color-primary);
        }
      `}</style>
    </div>
  )
}
