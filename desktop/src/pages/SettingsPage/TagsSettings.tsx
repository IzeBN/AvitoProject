import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi, type Tag } from '@/api/settings'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUIStore } from '@/stores/ui.store'
import { Plus, Trash2, Check, Pencil } from 'lucide-react'

const PRESET_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#ec4899', '#64748b',
]

interface TagFormState {
  name: string
  color: string
}

const defaultForm = (): TagFormState => ({ name: '', color: PRESET_COLORS[0] })

export default function TagsSettings() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [showAddModal, setShowAddModal] = useState(false)
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [formState, setFormState] = useState<TagFormState>(defaultForm())
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  const { data: tags, isLoading, isError } = useQuery({
    queryKey: ['settings', 'tags'],
    queryFn: () => settingsApi.getTags(),
    staleTime: 60_000,
  })

  const createTag = useMutation({
    mutationFn: (data: TagFormState) => settingsApi.createTag(data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'tags'] })
      showToast('success', 'Тег создан')
      setShowAddModal(false)
      setFormState(defaultForm())
    },
    onError: () => showToast('error', 'Не удалось создать тег'),
  })

  const updateTag = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Tag> }) =>
      settingsApi.updateTag(id, data),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'tags'] })
      showToast('success', 'Тег обновлён')
      setEditingTag(null)
    },
    onError: () => showToast('error', 'Не удалось обновить тег'),
  })

  const deleteTag = useMutation({
    mutationFn: (id: string) => settingsApi.deleteTag(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'tags'] })
      showToast('success', 'Тег удалён')
      setDeleteConfirmId(null)
    },
    onError: () => showToast('error', 'Не удалось удалить тег'),
  })

  const openEdit = (tag: Tag) => {
    setEditingTag(tag)
    setFormState({ name: tag.name, color: tag.color ?? PRESET_COLORS[0] })
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
        Не удалось загрузить теги
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 800 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          icon={<Plus size={15} />}
          size="sm"
          onClick={() => {
            setFormState(defaultForm())
            setShowAddModal(true)
          }}
        >
          Добавить тег
        </Button>
      </div>

      {!tags?.length ? (
        <EmptyState title="Тегов нет" description="Создайте теги для классификации кандидатов" />
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-start' }}>
          {tags.map(tag => (
            <div
              key={tag.id}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <Badge color={tag.color ?? undefined}>{tag.name}</Badge>
              <button
                onClick={() => openEdit(tag)}
                title="Редактировать"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  color: 'var(--color-text-secondary)',
                  padding: 2,
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                <Pencil size={12} />
              </button>
              <button
                onClick={() => setDeleteConfirmId(tag.id)}
                title="Удалить"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  color: 'var(--color-danger)',
                  padding: 2,
                  borderRadius: 4,
                  cursor: 'pointer',
                  opacity: 0.7,
                }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit modal */}
      <Modal
        open={showAddModal || editingTag !== null}
        onClose={() => {
          setShowAddModal(false)
          setEditingTag(null)
        }}
        title={editingTag ? 'Редактировать тег' : 'Новый тег'}
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setShowAddModal(false)
                setEditingTag(null)
              }}
            >
              Отмена
            </Button>
            <Button
              loading={createTag.isPending || updateTag.isPending}
              disabled={!formState.name.trim()}
              onClick={() => {
                if (editingTag) {
                  updateTag.mutate({ id: editingTag.id, data: formState })
                } else {
                  createTag.mutate(formState)
                }
              }}
            >
              {editingTag ? 'Сохранить' : 'Создать'}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Input
            label="Название"
            placeholder="Например: Срочно"
            value={formState.name}
            onChange={e => setFormState(s => ({ ...s, name: e.target.value }))}
          />
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Цвет</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
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
            {/* Preview */}
            <div style={{ marginTop: 12 }}>
              <Badge color={formState.color}>{formState.name || 'Предпросмотр'}</Badge>
            </div>
          </div>
        </div>
      </Modal>

      {/* Delete confirm */}
      <Modal
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        title="Удалить тег?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteConfirmId(null)}>
              Отмена
            </Button>
            <Button
              variant="danger"
              loading={deleteTag.isPending}
              onClick={() => {
                if (deleteConfirmId) deleteTag.mutate(deleteConfirmId)
              }}
            >
              Удалить
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Тег будет удалён у всех кандидатов, которым он присвоен.
        </p>
      </Modal>
    </div>
  )
}
