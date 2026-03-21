import { useState, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Plus, AlertTriangle, Calendar, Check, Trash2, User, Clock } from 'lucide-react'
import { useTasks, useUpdateTask, useCreateTask } from '@/hooks/useTasks'
import { tasksApi } from '@/api/tasks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Spinner } from '@/components/ui/Spinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useUIStore } from '@/stores/ui.store'
import { useAuthStore } from '@/stores/auth.store'
import { useQuery } from '@tanstack/react-query'
import { usersApi } from '@/api/users'
import type { Task } from '@/api/tasks'

type GroupKey = 'overdue' | 'today' | 'tomorrow' | 'this_week' | 'later' | 'done'

interface TaskGroup {
  key: GroupKey
  label: string
  tasks: Task[]
}

const getGroupKey = (task: Task): GroupKey => {
  if (task.status === 'done') return 'done'
  if (!task.due_date) return 'later'

  const now = new Date()
  const due = new Date(task.due_date)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  const nextWeek = new Date(today)
  nextWeek.setDate(today.getDate() + 7)
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate())

  if (dueDay < today) return 'overdue'
  if (dueDay.getTime() === today.getTime()) return 'today'
  if (dueDay.getTime() === tomorrow.getTime()) return 'tomorrow'
  if (dueDay < nextWeek) return 'this_week'
  return 'later'
}

const GROUP_ORDER: GroupKey[] = ['overdue', 'today', 'tomorrow', 'this_week', 'later', 'done']

const GROUP_CONFIG: Record<GroupKey, { label: string; icon: React.ReactNode; color?: string }> = {
  overdue: { label: 'Просроченные', icon: <AlertTriangle size={14} />, color: 'var(--color-danger)' },
  today: { label: 'Сегодня', icon: <Clock size={14} />, color: 'var(--color-primary)' },
  tomorrow: { label: 'Завтра', icon: <Calendar size={14} /> },
  this_week: { label: 'На этой неделе', icon: <Calendar size={14} /> },
  later: { label: 'Позже', icon: <Calendar size={14} /> },
  done: { label: 'Выполненные', icon: <Check size={14} />, color: 'var(--color-success)' },
}

const PRIORITY_CONFIG = {
  low: { label: 'Низкий', variant: 'default' as const },
  medium: { label: 'Средний', variant: 'warning' as const },
  high: { label: 'Высокий', variant: 'danger' as const },
}

const formatDueDate = (iso: string | null) => {
  if (!iso) return null
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
}

interface CreateTaskFormData {
  title: string
  description: string
  priority: Task['priority']
  assignee_id: string
  candidate_id: string
  due_date: string
}

export default function TasksPage() {
  const showToast = useUIStore(s => s.showToast)
  const currentUser = useAuthStore(s => s.user)
  const queryClient = useQueryClient()

  const [assigneeFilter, setAssigneeFilter] = useState('')
  const [dueDateFrom, setDueDateFrom] = useState('')
  const [dueDateTo, setDueDateTo] = useState('')
  const [onlyMine, setOnlyMine] = useState(false)
  const [onlyActive, setOnlyActive] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<GroupKey>>(new Set(['done']))
  const [createForm, setCreateForm] = useState<CreateTaskFormData>({
    title: '',
    description: '',
    priority: 'medium',
    assignee_id: '',
    candidate_id: '',
    due_date: '',
  })

  const { data: tasks = [], isLoading } = useTasks(
    assigneeFilter ? { assignee_id: assigneeFilter } : undefined
  )
  const updateTask = useUpdateTask()
  const createTask = useCreateTask()

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.getList(),
    staleTime: 60_000,
  })

  const filteredTasks = useMemo(() => {
    let result = tasks
    if (onlyMine && currentUser) {
      result = result.filter(t => t.assignee?.id === currentUser.id)
    }
    if (onlyActive) {
      result = result.filter(t => t.status !== 'done')
    }
    if (dueDateFrom) {
      result = result.filter(t => t.due_date && t.due_date >= dueDateFrom)
    }
    if (dueDateTo) {
      result = result.filter(t => t.due_date && t.due_date <= dueDateTo + 'T23:59:59')
    }
    return result
  }, [tasks, onlyMine, onlyActive, dueDateFrom, dueDateTo, currentUser])

  const groups = useMemo<TaskGroup[]>(() => {
    const map = new Map<GroupKey, Task[]>()
    GROUP_ORDER.forEach(key => map.set(key, []))
    filteredTasks.forEach(task => {
      const key = getGroupKey(task)
      map.get(key)!.push(task)
    })
    return GROUP_ORDER
      .map(key => ({ key, label: GROUP_CONFIG[key].label, tasks: map.get(key)! }))
      .filter(g => g.tasks.length > 0)
  }, [filteredTasks])

  const handleComplete = async (task: Task) => {
    try {
      await updateTask.mutateAsync({ id: task.id, data: { status: 'done' } })
      showToast('success', 'Задача выполнена')
    } catch {
      showToast('error', 'Не удалось обновить задачу')
    }
  }

  const handleDelete = async (taskId: string) => {
    if (!confirm('Удалить задачу?')) return
    try {
      await tasksApi.delete(taskId)
      showToast('success', 'Задача удалена')
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
    } catch {
      showToast('error', 'Не удалось удалить задачу')
    }
  }

  const handleCreate = async () => {
    if (!createForm.title.trim()) return
    try {
      await createTask.mutateAsync({
        title: createForm.title.trim(),
        description: createForm.description || null,
        status: 'open',
        priority: createForm.priority,
        responsible_id: createForm.assignee_id || null,
        candidate_id: createForm.candidate_id || null,
        due_date: createForm.due_date || null,
      })
      showToast('success', 'Задача создана')
      setCreateOpen(false)
      setCreateForm({ title: '', description: '', priority: 'medium', assignee_id: '', candidate_id: '', due_date: '' })
    } catch {
      showToast('error', 'Не удалось создать задачу')
    }
  }

  const toggleGroup = (key: GroupKey) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div className="tp-page">
      {/* Заголовок */}
      <div className="tp-header">
        <h1 className="tp-title">Задачи</h1>
        <Button variant="primary" icon={<Plus size={14} />} onClick={() => setCreateOpen(true)}>
          Создать задачу
        </Button>
      </div>

      <div className="tp-layout">
        {/* Фильтры */}
        <aside className="tp-filters">
          <div className="tp-filter-section">
            <label className="tp-filter-label">Ответственный</label>
            <select
              className="tp-filter-select"
              value={assigneeFilter}
              onChange={e => setAssigneeFilter(e.target.value)}
            >
              <option value="">Все</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.full_name}</option>
              ))}
            </select>
          </div>

          <div className="tp-filter-section">
            <label className="tp-filter-label">Период</label>
            <input
              type="date"
              className="tp-filter-date"
              value={dueDateFrom}
              onChange={e => setDueDateFrom(e.target.value)}
              placeholder="От"
            />
            <input
              type="date"
              className="tp-filter-date"
              value={dueDateTo}
              onChange={e => setDueDateTo(e.target.value)}
              placeholder="До"
              style={{ marginTop: 6 }}
            />
          </div>

          <div className="tp-filter-section">
            <label className="tp-filter-check">
              <input
                type="checkbox"
                checked={onlyMine}
                onChange={e => setOnlyMine(e.target.checked)}
              />
              <span>Только мои</span>
            </label>
            <label className="tp-filter-check">
              <input
                type="checkbox"
                checked={onlyActive}
                onChange={e => setOnlyActive(e.target.checked)}
              />
              <span>Только активные</span>
            </label>
          </div>
        </aside>

        {/* Список задач */}
        <main className="tp-main">
          {isLoading ? (
            <div className="tp-loading"><Spinner size="lg" /></div>
          ) : groups.length === 0 ? (
            <EmptyState
              title="Нет задач"
              description="Создайте первую задачу"
              action={
                <Button icon={<Plus size={14} />} onClick={() => setCreateOpen(true)}>
                  Создать задачу
                </Button>
              }
            />
          ) : (
            groups.map(group => {
              const cfg = GROUP_CONFIG[group.key]
              const collapsed = collapsedGroups.has(group.key)
              return (
                <div key={group.key} className="tp-group">
                  <button
                    className="tp-group-header"
                    onClick={() => toggleGroup(group.key)}
                    style={cfg.color ? { color: cfg.color } : undefined}
                    aria-expanded={!collapsed}
                  >
                    <span className="tp-group-icon">{cfg.icon}</span>
                    <span className="tp-group-label">{group.label}</span>
                    <span className="tp-group-count">{group.tasks.length}</span>
                    <span className="tp-group-chevron">{collapsed ? '▶' : '▼'}</span>
                  </button>

                  {!collapsed && (
                    <div className="tp-task-list">
                      {group.tasks.map(task => (
                        <div
                          key={task.id}
                          className={`tp-task ${group.key === 'overdue' ? 'tp-task--overdue' : ''} ${task.status === 'done' ? 'tp-task--done' : ''}`}
                        >
                          <div className="tp-task-main">
                            <div className="tp-task-title-row">
                              <span className="tp-task-title">{task.title}</span>
                              <Badge variant={PRIORITY_CONFIG[task.priority].variant}>
                                {PRIORITY_CONFIG[task.priority].label}
                              </Badge>
                            </div>
                            {task.description && (
                              <p className="tp-task-desc">{task.description}</p>
                            )}
                            <div className="tp-task-meta">
                              {task.assignee && (
                                <span className="tp-task-meta-item">
                                  <User size={12} />
                                  {task.assignee.full_name}
                                </span>
                              )}
                              {task.due_date && (
                                <span
                                  className={`tp-task-meta-item ${group.key === 'overdue' ? 'tp-task-meta-item--danger' : ''}`}
                                >
                                  <Calendar size={12} />
                                  до {formatDueDate(task.due_date)}
                                </span>
                              )}
                              {task.candidate && (
                                <span className="tp-task-meta-item">
                                  {task.candidate.name ?? 'Кандидат'}
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="tp-task-actions">
                            {task.status !== 'done' && (
                              <button
                                className="tp-task-btn tp-task-btn--complete"
                                onClick={() => void handleComplete(task)}
                                disabled={updateTask.isPending}
                                aria-label="Выполнено"
                                title="Отметить выполненным"
                              >
                                <Check size={14} />
                                Выполнено
                              </button>
                            )}
                            <button
                              className="tp-task-btn tp-task-btn--delete"
                              onClick={() => void handleDelete(task.id)}
                              disabled={updateTask.isPending}
                              aria-label="Удалить"
                              title="Удалить задачу"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </main>
      </div>

      {/* Модал создания задачи */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Создать задачу"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Отмена</Button>
            <Button
              onClick={() => void handleCreate()}
              loading={createTask.isPending}
              disabled={!createForm.title.trim()}
            >
              Создать
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input
            label="Название *"
            placeholder="Введите название задачи..."
            value={createForm.title}
            onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))}
          />

          <div className="tp-modal-field">
            <label className="tp-modal-label">Описание</label>
            <textarea
              className="tp-modal-textarea"
              placeholder="Опционально..."
              value={createForm.description}
              onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))}
              rows={3}
            />
          </div>

          <div className="tp-modal-row">
            <div className="tp-modal-field" style={{ flex: 1 }}>
              <label className="tp-modal-label">Приоритет</label>
              <select
                className="tp-modal-select"
                value={createForm.priority}
                onChange={e => setCreateForm(f => ({ ...f, priority: e.target.value as Task['priority'] }))}
              >
                <option value="low">Низкий</option>
                <option value="medium">Средний</option>
                <option value="high">Высокий</option>
              </select>
            </div>

            <div className="tp-modal-field" style={{ flex: 1 }}>
              <label className="tp-modal-label">Срок выполнения</label>
              <input
                type="date"
                className="tp-modal-input"
                value={createForm.due_date}
                onChange={e => setCreateForm(f => ({ ...f, due_date: e.target.value }))}
              />
            </div>
          </div>

          <div className="tp-modal-field">
            <label className="tp-modal-label">Ответственный</label>
            <select
              className="tp-modal-select"
              value={createForm.assignee_id}
              onChange={e => setCreateForm(f => ({ ...f, assignee_id: e.target.value }))}
            >
              <option value="">Не назначен</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.full_name}</option>
              ))}
            </select>
          </div>
        </div>
      </Modal>

      <style>{`
        .tp-page {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .tp-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px 24px 16px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          flex-shrink: 0;
        }
        .tp-title { font-size: 20px; font-weight: 700; }
        .tp-layout {
          display: flex;
          flex: 1;
          overflow: hidden;
        }
        .tp-filters {
          width: 220px;
          border-right: 1px solid var(--color-border);
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 4px;
          overflow-y: auto;
          background: var(--color-surface);
          flex-shrink: 0;
        }
        .tp-filter-section {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 10px 0;
          border-bottom: 1px solid var(--color-border);
        }
        .tp-filter-label {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-secondary);
        }
        .tp-filter-select, .tp-filter-date {
          width: 100%;
          padding: 7px 10px;
          font-size: 13px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
        }
        .tp-filter-select:focus, .tp-filter-date:focus {
          border-color: var(--color-primary);
        }
        .tp-filter-check {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          color: var(--color-text);
          cursor: pointer;
        }
        .tp-main {
          flex: 1;
          overflow-y: auto;
          padding: 16px 24px;
        }
        .tp-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 80px;
        }
        .tp-group { margin-bottom: 16px; }
        .tp-group-header {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          text-align: left;
          padding: 8px 0;
          font-size: 14px;
          font-weight: 600;
          color: var(--color-text);
          transition: opacity 0.15s;
        }
        .tp-group-header:hover { opacity: 0.8; }
        .tp-group-icon { display: flex; align-items: center; }
        .tp-group-label { flex: 1; }
        .tp-group-count {
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 999px;
          padding: 1px 8px;
          font-size: 12px;
          font-weight: 500;
          color: var(--color-text-secondary);
        }
        .tp-group-chevron { font-size: 10px; color: var(--color-text-secondary); }
        .tp-task-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding-left: 8px;
        }
        .tp-task {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 14px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          transition: box-shadow 0.15s;
        }
        .tp-task:hover { box-shadow: var(--shadow-sm); }
        .tp-task--overdue { border-left: 3px solid var(--color-danger); }
        .tp-task--done { opacity: 0.6; }
        .tp-task-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
        .tp-task-title-row {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .tp-task-title {
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text);
          flex: 1;
          min-width: 0;
        }
        .tp-task--done .tp-task-title {
          text-decoration: line-through;
          color: var(--color-text-secondary);
        }
        .tp-task-desc {
          font-size: 13px;
          color: var(--color-text-secondary);
          line-height: 1.4;
        }
        .tp-task-meta {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }
        .tp-task-meta-item {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 12px;
          color: var(--color-text-secondary);
        }
        .tp-task-meta-item--danger { color: var(--color-danger); font-weight: 500; }
        .tp-task-actions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }
        .tp-task-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 5px 10px;
          border-radius: var(--radius-sm);
          font-size: 12px;
          font-weight: 500;
          transition: all 0.15s;
        }
        .tp-task-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .tp-task-btn--complete {
          background: #dcfce7;
          color: #15803d;
          border: 1px solid #bbf7d0;
        }
        .tp-task-btn--complete:hover:not(:disabled) { background: #bbf7d0; }
        .tp-task-btn--delete {
          background: transparent;
          color: var(--color-text-secondary);
          border: 1px solid transparent;
          padding: 5px;
        }
        .tp-task-btn--delete:hover:not(:disabled) {
          background: #fee2e2;
          color: var(--color-danger);
          border-color: #fecaca;
        }
        .tp-modal-field { display: flex; flex-direction: column; gap: 6px; }
        .tp-modal-label { font-size: 13px; font-weight: 500; color: var(--color-text); }
        .tp-modal-textarea {
          width: 100%;
          padding: 8px 12px;
          font-size: 14px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          resize: vertical;
          outline: none;
          font-family: inherit;
        }
        .tp-modal-textarea:focus { border-color: var(--color-primary); }
        .tp-modal-select, .tp-modal-input {
          width: 100%;
          padding: 8px 12px;
          font-size: 14px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
        }
        .tp-modal-select:focus, .tp-modal-input:focus { border-color: var(--color-primary); }
        .tp-modal-row { display: flex; gap: 12px; }
      `}</style>
    </div>
  )
}
