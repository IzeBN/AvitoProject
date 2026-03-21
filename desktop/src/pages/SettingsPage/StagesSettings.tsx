import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi, type Stage } from '@/api/settings'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUIStore } from '@/stores/ui.store'
import { Plus, Trash2, GripVertical, Check } from 'lucide-react'

const PRESET_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#ec4899', '#64748b',
]

interface StageFormState {
  name: string
  color: string
}

export default function StagesSettings() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [showAddModal, setShowAddModal] = useState(false)
  const [formState, setFormState] = useState<StageFormState>({ name: '', color: PRESET_COLORS[0] })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  // DnD state
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [dragOverId, setDragOverId] = useState<string | null>(null)
  const orderedRef = useRef<Stage[]>([])

  const { data: stages, isLoading, isError } = useQuery({
    queryKey: ['settings', 'stages'],
    queryFn: () => settingsApi.getStages(),
    staleTime: 60_000,
  })

  const createStage = useMutation({
    mutationFn: (data: { name: string; color: string }) =>
      settingsApi.createStage({ ...data, order: 0 }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'stages'] })
      showToast('success', 'Этап создан')
      setShowAddModal(false)
      setFormState({ name: '', color: PRESET_COLORS[0] })
    },
    onError: () => showToast('error', 'Не удалось создать этап'),
  })

  const updateStage = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Stage> }) =>
      settingsApi.updateStage(id, data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'stages'] })
      setEditingId(null)
    },
    onError: () => showToast('error', 'Не удалось обновить этап'),
  })

  const deleteStage = useMutation({
    mutationFn: (id: string) => settingsApi.deleteStage(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'stages'] })
      showToast('success', 'Этап удалён')
      setDeleteConfirmId(null)
    },
    onError: () => showToast('error', 'Не удалось удалить этап'),
  })

  const reorderStages = useMutation({
    mutationFn: (ids: string[]) => settingsApi.reorderStages(ids),
    onError: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'stages'] })
      showToast('error', 'Не удалось сохранить порядок')
    },
  })

  // Локальный список для оптимистичного ре-ордера
  const displayStages = orderedRef.current.length > 0 && draggedId
    ? orderedRef.current
    : (stages ?? [])

  const handleDragStart = (id: string) => {
    setDraggedId(id)
    orderedRef.current = [...(stages ?? [])]
  }

  const handleDragOver = (e: React.DragEvent, overId: string) => {
    e.preventDefault()
    if (overId === draggedId) return
    setDragOverId(overId)

    const current = [...orderedRef.current]
    const fromIdx = current.findIndex(s => s.id === draggedId)
    const toIdx = current.findIndex(s => s.id === overId)
    if (fromIdx === -1 || toIdx === -1) return
    const [item] = current.splice(fromIdx, 1)
    current.splice(toIdx, 0, item)
    orderedRef.current = current
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const ids = orderedRef.current.map(s => s.id)
    // Optimistic update в кэше
    qc.setQueryData<Stage[]>(['settings', 'stages'], orderedRef.current)
    reorderStages.mutate(ids)
    setDraggedId(null)
    setDragOverId(null)
    orderedRef.current = []
  }

  const handleDragEnd = () => {
    setDraggedId(null)
    setDragOverId(null)
    orderedRef.current = []
  }

  const startEdit = (stage: Stage) => {
    setEditingId(stage.id)
    setEditingName(stage.name)
  }

  const confirmEdit = (stage: Stage) => {
    const trimmed = editingName.trim()
    if (!trimmed || trimmed === stage.name) {
      setEditingId(null)
      return
    }
    updateStage.mutate({ id: stage.id, data: { name: trimmed } })
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
        <Spinner />
      </div>
    )
  }

  if (isError) {
    return (
      <div style={{ color: 'var(--color-danger)', padding: 16, fontSize: 14 }}>
        Не удалось загрузить этапы
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 560 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button icon={<Plus size={15} />} size="sm" onClick={() => setShowAddModal(true)}>
          Добавить этап
        </Button>
      </div>

      {!displayStages.length ? (
        <EmptyState title="Этапов нет" description="Создайте первый этап воронки" />
      ) : (
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
        >
          {displayStages.map(stage => (
            <div
              key={stage.id}
              draggable
              onDragStart={() => handleDragStart(stage.id)}
              onDragOver={e => handleDragOver(e, stage.id)}
              onDragEnd={handleDragEnd}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                background: 'var(--color-surface)',
                border: `1px solid ${dragOverId === stage.id ? 'var(--color-primary)' : 'var(--color-border)'}`,
                borderRadius: 'var(--radius-sm)',
                opacity: draggedId === stage.id ? 0.4 : 1,
                cursor: 'default',
                transition: 'border-color 0.1s',
              }}
            >
              <span
                style={{ color: 'var(--color-text-secondary)', cursor: 'grab', display: 'flex' }}
                title="Перетащить"
              >
                <GripVertical size={16} />
              </span>

              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: stage.color ?? '#64748b',
                  flexShrink: 0,
                }}
              />

              {editingId === stage.id ? (
                <input
                  autoFocus
                  value={editingName}
                  onChange={e => setEditingName(e.target.value)}
                  onBlur={() => confirmEdit(stage)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') confirmEdit(stage)
                    if (e.key === 'Escape') setEditingId(null)
                  }}
                  style={{
                    flex: 1,
                    fontSize: 14,
                    fontWeight: 500,
                    border: '1px solid var(--color-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '2px 6px',
                    outline: 'none',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                  }}
                />
              ) : (
                <span
                  style={{ flex: 1, fontSize: 14, fontWeight: 500, cursor: 'text' }}
                  onDoubleClick={() => startEdit(stage)}
                  title="Двойной клик для редактирования"
                >
                  {stage.name}
                </span>
              )}

              {/* Color picker */}
              <div style={{ display: 'flex', gap: 3 }}>
                {PRESET_COLORS.map(color => (
                  <button
                    key={color}
                    title={color}
                    onClick={() => updateStage.mutate({ id: stage.id, data: { color } })}
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: '50%',
                      background: color,
                      border: stage.color === color ? '2px solid var(--color-text)' : '2px solid transparent',
                      cursor: 'pointer',
                      flexShrink: 0,
                      transition: 'border-color 0.1s',
                    }}
                  />
                ))}
              </div>

              <Button
                variant="ghost"
                size="sm"
                icon={<Trash2 size={14} />}
                onClick={() => setDeleteConfirmId(stage.id)}
                aria-label={`Удалить этап ${stage.name}`}
              />
            </div>
          ))}
        </div>
      )}

      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
        Перетащите этапы чтобы изменить порядок. Двойной клик по названию — редактировать.
      </p>

      {/* Add modal */}
      <Modal
        open={showAddModal}
        onClose={() => {
          setShowAddModal(false)
          setFormState({ name: '', color: PRESET_COLORS[0] })
        }}
        title="Новый этап"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>
              Отмена
            </Button>
            <Button
              loading={createStage.isPending}
              disabled={!formState.name.trim()}
              onClick={() => createStage.mutate(formState)}
            >
              Создать
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Input
            label="Название"
            placeholder="Например: Телефонное интервью"
            value={formState.name}
            onChange={e => setFormState(s => ({ ...s, name: e.target.value }))}
            onKeyDown={e => {
              if (e.key === 'Enter' && formState.name.trim()) {
                createStage.mutate(formState)
              }
            }}
          />
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Цвет</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {PRESET_COLORS.map(color => (
                <button
                  key={color}
                  onClick={() => setFormState(s => ({ ...s, color }))}
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    background: color,
                    border: formState.color === color
                      ? '3px solid var(--color-text)'
                      : '3px solid transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'border-color 0.1s',
                  }}
                >
                  {formState.color === color && <Check size={14} color="#fff" strokeWidth={3} />}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>

      {/* Delete confirm modal */}
      <Modal
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        title="Удалить этап?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteConfirmId(null)}>
              Отмена
            </Button>
            <Button
              variant="danger"
              loading={deleteStage.isPending}
              onClick={() => {
                if (deleteConfirmId) deleteStage.mutate(deleteConfirmId)
              }}
            >
              Удалить
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Это действие нельзя отменить. Кандидаты в этом этапе останутся без этапа.
        </p>
      </Modal>
    </div>
  )
}
