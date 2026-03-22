import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi, type Department } from '@/api/settings'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUIStore } from '@/stores/ui.store'
import { Plus, Trash2, Check, X } from 'lucide-react'

export default function DepartmentsSettings() {
  const qc = useQueryClient()
  const showToast = useUIStore(s => s.showToast)

  const [showAddModal, setShowAddModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')

  const { data: departments, isLoading, isError } = useQuery({
    queryKey: ['settings', 'departments'],
    queryFn: () => settingsApi.getDepartments(),
    staleTime: 60_000,
  })

  const createDept = useMutation({
    mutationFn: (name: string) => settingsApi.createDepartment({ name, description: null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'departments'] })
      showToast('success', 'Отдел создан')
      setShowAddModal(false)
      setNewName('')
    },
    onError: () => showToast('error', 'Не удалось создать отдел'),
  })

  const updateDept = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      settingsApi.updateDepartment(id, { name, description: null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'departments'] })
      setEditingId(null)
    },
    onError: () => showToast('error', 'Не удалось обновить отдел'),
  })

  const deleteDept = useMutation({
    mutationFn: (id: string) => settingsApi.deleteDepartment(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['settings', 'departments'] })
      showToast('success', 'Отдел удалён')
      setDeleteConfirmId(null)
    },
    onError: () => showToast('error', 'Не удалось удалить отдел'),
  })

  const startEdit = (dept: Department) => {
    setEditingId(dept.id)
    setEditingName(dept.name)
  }

  const confirmEdit = (id: string, originalName: string) => {
    const trimmed = editingName.trim()
    if (!trimmed || trimmed === originalName) {
      setEditingId(null)
      return
    }
    updateDept.mutate({ id, name: trimmed })
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
        Не удалось загрузить отделы
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 800 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button icon={<Plus size={15} />} size="sm" onClick={() => setShowAddModal(true)}>
          Добавить отдел
        </Button>
      </div>

      {!departments?.length ? (
        <EmptyState
          title="Отделов нет"
          description="Создайте отделы для группировки вакансий и кандидатов"
        />
      ) : (
        <div
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
          }}
        >
          {departments.map((dept, i) => (
            <div
              key={dept.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '11px 16px',
                borderBottom: i < departments.length - 1
                  ? '1px solid var(--color-border)'
                  : 'none',
              }}
            >
              {editingId === dept.id ? (
                <>
                  <input
                    autoFocus
                    value={editingName}
                    onChange={e => setEditingName(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') confirmEdit(dept.id, dept.name)
                      if (e.key === 'Escape') setEditingId(null)
                    }}
                    style={{
                      flex: 1,
                      fontSize: 14,
                      fontWeight: 500,
                      border: '1px solid var(--color-primary)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '4px 8px',
                      outline: 'none',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                    }}
                  />
                  <button
                    onClick={() => confirmEdit(dept.id, dept.name)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      color: 'var(--color-success)',
                      padding: 4,
                    }}
                    title="Сохранить"
                  >
                    <Check size={15} />
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      color: 'var(--color-text-secondary)',
                      padding: 4,
                    }}
                    title="Отмена"
                  >
                    <X size={15} />
                  </button>
                </>
              ) : (
                <>
                  <span
                    style={{ flex: 1, fontSize: 14, fontWeight: 500, cursor: 'pointer' }}
                    onDoubleClick={() => startEdit(dept)}
                    title="Двойной клик для редактирования"
                  >
                    {dept.name}
                  </span>
                  {dept.description && (
                    <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
                      {dept.description}
                    </span>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Trash2 size={14} />}
                    onClick={() => setDeleteConfirmId(dept.id)}
                    aria-label={`Удалить отдел ${dept.name}`}
                  />
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
        Двойной клик по названию — редактировать.
      </p>

      {/* Add modal */}
      <Modal
        open={showAddModal}
        onClose={() => {
          setShowAddModal(false)
          setNewName('')
        }}
        title="Новый отдел"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>
              Отмена
            </Button>
            <Button
              loading={createDept.isPending}
              disabled={!newName.trim()}
              onClick={() => createDept.mutate(newName.trim())}
            >
              Создать
            </Button>
          </>
        }
      >
        <Input
          label="Название отдела"
          placeholder="Например: Москва"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && newName.trim()) createDept.mutate(newName.trim())
          }}
        />
      </Modal>

      {/* Delete confirm */}
      <Modal
        open={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        title="Удалить отдел?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteConfirmId(null)}>
              Отмена
            </Button>
            <Button
              variant="danger"
              loading={deleteDept.isPending}
              onClick={() => {
                if (deleteConfirmId) deleteDept.mutate(deleteConfirmId)
              }}
            >
              Удалить
            </Button>
          </>
        }
      >
        <p style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          Сотрудники и вакансии в этом отделе не будут удалены, но потеряют привязку.
        </p>
      </Modal>
    </div>
  )
}
