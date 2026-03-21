import { useState, useCallback, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Plus, Download, SlidersHorizontal } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useCandidates, useBulkEditCandidates } from '@/hooks/useCandidates'
import { useDebounce } from '@/hooks/useDebounce'
import { Button } from '@/components/ui/Button'
import { Pagination } from '@/components/ui/Pagination'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { CandidateTable } from '@/components/candidates/CandidateTable'
import { CandidateFilters } from '@/components/candidates/CandidateFilters'
import { CandidateModal } from '@/components/candidates/CandidateModal'
import { BulkActionsBar } from '@/components/candidates/BulkActionsBar'
import { StageSelect } from '@/components/candidates/StageSelect'
import { StartMailingModal } from '@/components/mailings/StartMailingModal'
import { FilterMailingModal } from '@/components/mailings/FilterMailingModal'
import { Send } from 'lucide-react'
import { useUIStore } from '@/stores/ui.store'
import { wsManager } from '@/api/websocket'
import { candidatesApi } from '@/api/candidates'
import { useQuery } from '@tanstack/react-query'
import { usersApi } from '@/api/users'
import { avitoAccountsApi } from '@/api/avito-accounts'
import { settingsApi } from '@/api/settings'
import type { CandidateFilters as Filters } from '@/types/candidate'
import type { Candidate } from '@/types/candidate'


const EMPTY_FILTERS: Filters = {}

function filtersFromParams(params: URLSearchParams): Filters {
  return {
    stage_id: params.get('stage_id') ?? undefined,
    responsible_id: params.get('responsible_id') ?? undefined,
    department_id: params.get('department_id') ?? undefined,
    avito_account_id: params.get('avito_account_id') ?? undefined,
    tag_ids: params.getAll('tag_ids').length ? params.getAll('tag_ids') : undefined,
    has_new_message: params.get('has_new_message') === 'true' || undefined,
    created_at_from: params.get('created_at_from') ?? undefined,
    created_at_to: params.get('created_at_to') ?? undefined,
    due_date_from: params.get('due_date_from') ?? undefined,
    due_date_to: params.get('due_date_to') ?? undefined,
  }
}

function filtersToParams(filters: Filters, search: string, page: number): URLSearchParams {
  const p = new URLSearchParams()
  if (search) p.set('search', search)
  if (page > 1) p.set('page', String(page))
  Object.entries(filters).forEach(([k, v]) => {
    if (v === undefined || v === null) return
    if (Array.isArray(v)) v.forEach(item => p.append(k, item))
    else p.set(k, String(v))
  })
  return p
}

export default function CandidatesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const showToast = useUIStore(s => s.showToast)
  const queryClient = useQueryClient()

  const [filtersOpen, setFiltersOpen] = useState(() => {
    const stored = localStorage.getItem('cp_filters_open')
    return stored !== null ? stored === 'true' : true
  })
  const [page, setPage] = useState(() => Number(searchParams.get('page') ?? 1))
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [filters, setFilters] = useState<Filters>(() => filtersFromParams(searchParams))
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [openCandidateId, setOpenCandidateId] = useState<string | null>(null)
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set())

  // Bulk action modals
  const [bulkStageOpen, setBulkStageOpen] = useState(false)
  const [bulkStageId, setBulkStageId] = useState('')
  const [bulkResponsibleOpen, setBulkResponsibleOpen] = useState(false)
  const [bulkResponsibleId, setBulkResponsibleId] = useState('')

  // Add candidate modal
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [addForm, setAddForm] = useState({ full_name: '', phone: '' })
  const [addLoading, setAddLoading] = useState(false)

  // Mailing modals
  const [mailingModalOpen, setMailingModalOpen] = useState(false)
  const [filterMailingOpen, setFilterMailingOpen] = useState(false)

  const debouncedSearch = useDebounce(search, 400)
  const bulkEdit = useBulkEditCandidates()

  const activeFilters: Filters = { ...filters, search: debouncedSearch || undefined }
  const activeFiltersCount = Object.values(activeFilters).filter(v => v !== undefined && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)).length
  const { data, isLoading } = useCandidates(activeFilters, page)

  // Пользователи для фильтра "ответственный"
  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.getList(),
    staleTime: 60_000,
  })

  // Этапы
  const { data: stages = [] } = useQuery({
    queryKey: ['stages'],
    queryFn: () => settingsApi.getStages(),
    staleTime: 5 * 60_000,
  })

  // Теги
  const { data: tags = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: () => settingsApi.getTags(),
    staleTime: 5 * 60_000,
  })

  // Отделы
  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: () => settingsApi.getDepartments(),
    staleTime: 5 * 60_000,
  })

  // Аккаунты Авито
  const { data: accounts = [] } = useQuery({
    queryKey: ['avito-accounts'],
    queryFn: () => avitoAccountsApi.getList(),
    staleTime: 60_000,
  })

  // Синхронизация URL params
  useEffect(() => {
    setSearchParams(filtersToParams(filters, search, page), { replace: true })
  }, [filters, search, page, setSearchParams])

  // WS: подсветка строки при новом сообщении
  useEffect(() => {
    const unsub = wsManager.on('new_message', (msg) => {
      const candidateId = String(msg.candidate_id ?? '')
      if (!candidateId) return
      setHighlightedIds(prev => new Set([...prev, candidateId]))
      setTimeout(() => {
        setHighlightedIds(prev => {
          const next = new Set(prev)
          next.delete(candidateId)
          return next
        })
      }, 2000)
    })
    return unsub
  }, [])

  const handleSearchChange = useCallback((v: string) => {
    setSearch(v)
    setPage(1)
  }, [])

  const handleFiltersChange = useCallback((f: Filters) => {
    setFilters(f)
    setPage(1)
    setSelectedKeys(new Set())
  }, [])

  const handleReset = useCallback(() => {
    setFilters(EMPTY_FILTERS)
    setSearch('')
    setPage(1)
    setSelectedKeys(new Set())
  }, [])

  const handleSelectRow = useCallback((id: string, checked: boolean) => {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked) {
      setSelectedKeys(new Set(data?.items.map(c => c.id) ?? []))
    } else {
      setSelectedKeys(new Set())
    }
  }, [data?.items])

  const handleRowClick = useCallback((candidate: Candidate) => {
    setOpenCandidateId(candidate.id)
  }, [])

  const handleOpenChat = useCallback((candidate: Candidate) => {
    setOpenCandidateId(null)
    navigate(`/messenger?candidate_id=${candidate.id}`)
  }, [navigate])

  const handleBulkChangeStage = async () => {
    if (!bulkStageId) return
    try {
      await bulkEdit.mutateAsync({ ids: [...selectedKeys], edit: { stage_id: bulkStageId } })
      showToast('success', 'Этап изменён')
      setBulkStageOpen(false)
      setBulkStageId('')
      setSelectedKeys(new Set())
    } catch {
      showToast('error', 'Не удалось изменить этап')
    }
  }

  const handleBulkAssignResponsible = async () => {
    if (!bulkResponsibleId) return
    try {
      await bulkEdit.mutateAsync({ ids: [...selectedKeys], edit: { responsible_id: bulkResponsibleId } })
      showToast('success', 'Ответственный назначен')
      setBulkResponsibleOpen(false)
      setBulkResponsibleId('')
      setSelectedKeys(new Set())
    } catch {
      showToast('error', 'Не удалось назначить ответственного')
    }
  }

  const handleStartMailing = () => {
    setMailingModalOpen(true)
  }

  const handleAddCandidate = async () => {
    if (!addForm.full_name.trim()) return
    setAddLoading(true)
    try {
      await candidatesApi.create({
        full_name: addForm.full_name.trim(),
        phone: addForm.phone.trim() || undefined,
      })
      await queryClient.invalidateQueries({ queryKey: ['candidates'] })
      showToast('success', 'Кандидат добавлен')
      setAddModalOpen(false)
      setAddForm({ full_name: '', phone: '' })
    } catch {
      showToast('error', 'Не удалось добавить кандидата')
    } finally {
      setAddLoading(false)
    }
  }

  const handleExport = async () => {
    try {
      const blob = await candidatesApi.exportCsv()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `candidates_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      showToast('error', 'Не удалось экспортировать')
    }
  }

  const responsibles = users.map(u => ({ id: u.id, name: u.full_name }))
  const accountOptions = accounts.map(a => ({ id: a.id, name: a.name }))

  return (
    <div className="cp-page">
      {/* Заголовок */}
      <div className="cp-header">
        <h1 className="cp-title">
          Кандидаты
          {data?.total !== undefined && (
            <span className="cp-count">{data.total.toLocaleString('ru-RU')}</span>
          )}
        </h1>
        <div className="cp-header-actions">
          <Button
            variant="secondary"
            size="sm"
            icon={<SlidersHorizontal size={14} />}
            onClick={() => {
              const next = !filtersOpen
              setFiltersOpen(next)
              localStorage.setItem('cp_filters_open', String(next))
            }}
          >
            Фильтры
          </Button>
          {activeFiltersCount > 0 && (
            <Button
              variant="secondary"
              size="sm"
              icon={<Send size={14} />}
              onClick={() => setFilterMailingOpen(true)}
            >
              Рассылка по фильтрам ({activeFiltersCount})
            </Button>
          )}
          <Button variant="secondary" size="sm" icon={<Download size={14} />} onClick={() => void handleExport()}>
            Экспорт
          </Button>
          <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={() => setAddModalOpen(true)}>
            Добавить
          </Button>
        </div>
      </div>

      {/* Контент: фильтры + таблица */}
      <div className="cp-content">
        {filtersOpen && (
          <CandidateFilters
            filters={filters}
            search={search}
            onSearchChange={handleSearchChange}
            onChange={handleFiltersChange}
            onReset={handleReset}
            stages={stages}
            responsibles={responsibles}
            departments={departments}
            accounts={accountOptions}
            tags={tags}
          />
        )}

        <div className="cp-table-area">
          {!filtersOpen && (
            <div className="cp-inline-search">
              <input
                className="cp-inline-search-input"
                type="text"
                placeholder="Поиск кандидатов..."
                value={search}
                onChange={e => handleSearchChange(e.target.value)}
              />
            </div>
          )}
          <CandidateTable
            data={data?.items ?? []}
            loading={isLoading}
            selectedKeys={selectedKeys}
            onSelectRow={handleSelectRow}
            onSelectAll={handleSelectAll}
            onRowClick={handleRowClick}
            highlightedIds={highlightedIds}
          />

          <div className="cp-footer">
            <span className="cp-total">
              Всего: {data?.total?.toLocaleString('ru-RU') ?? 0}
            </span>
            <Pagination
              page={page}
              totalPages={data?.pages ?? 1}
              onPageChange={setPage}
            />
          </div>
        </div>
      </div>

      {/* Карточка кандидата */}
      <CandidateModal
        candidateId={openCandidateId}
        onClose={() => setOpenCandidateId(null)}
        onOpenChat={handleOpenChat}
        stages={stages}
        responsibles={responsibles}
        departments={departments}
        tags={tags}
      />

      {/* Bulk: сменить этап */}
      <Modal
        open={bulkStageOpen}
        onClose={() => setBulkStageOpen(false)}
        title="Сменить этап"
        footer={
          <>
            <Button variant="ghost" onClick={() => setBulkStageOpen(false)}>Отмена</Button>
            <Button onClick={() => void handleBulkChangeStage()} loading={bulkEdit.isPending} disabled={!bulkStageId}>
              Применить
            </Button>
          </>
        }
        size="sm"
      >
        <StageSelect
          stages={stages}
          value={bulkStageId}
          onChange={e => setBulkStageId(e.target.value)}
          placeholder="Выберите этап"
        />
      </Modal>

      {/* Bulk: назначить ответственного */}
      <Modal
        open={bulkResponsibleOpen}
        onClose={() => setBulkResponsibleOpen(false)}
        title="Назначить ответственного"
        footer={
          <>
            <Button variant="ghost" onClick={() => setBulkResponsibleOpen(false)}>Отмена</Button>
            <Button
              onClick={() => void handleBulkAssignResponsible()}
              loading={bulkEdit.isPending}
              disabled={!bulkResponsibleId}
            >
              Применить
            </Button>
          </>
        }
        size="sm"
      >
        <select
          className="cp-bulk-select"
          value={bulkResponsibleId}
          onChange={e => setBulkResponsibleId(e.target.value)}
        >
          <option value="">Выберите ответственного</option>
          {responsibles.map(r => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
      </Modal>

      {/* Добавить кандидата */}
      <Modal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        title="Добавить кандидата"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddModalOpen(false)}>Отмена</Button>
            <Button
              loading={addLoading}
              disabled={!addForm.full_name.trim()}
              onClick={() => void handleAddCandidate()}
            >
              Добавить
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Input
            label="ФИО *"
            placeholder="Иванов Иван Иванович"
            value={addForm.full_name}
            onChange={e => setAddForm(f => ({ ...f, full_name: e.target.value }))}
            autoFocus
          />
          <Input
            label="Телефон"
            placeholder="+7 900 000 00 00"
            value={addForm.phone}
            onChange={e => setAddForm(f => ({ ...f, phone: e.target.value }))}
          />
        </div>
      </Modal>

      {/* Рассылка по выбранным */}
      <StartMailingModal
        open={mailingModalOpen}
        onClose={() => setMailingModalOpen(false)}
        preselectedIds={[...selectedKeys]}
      />

      {/* Рассылка по фильтрам */}
      <FilterMailingModal
        open={filterMailingOpen}
        onClose={() => setFilterMailingOpen(false)}
        filters={activeFilters as Record<string, unknown>}
        filtersCount={activeFiltersCount}
      />

      {/* Панель массовых действий */}
      <BulkActionsBar
        selectedCount={selectedKeys.size}
        onClearSelection={() => setSelectedKeys(new Set())}
        onChangeStage={() => setBulkStageOpen(true)}
        onAssignResponsible={() => setBulkResponsibleOpen(true)}
        onAddTag={() => showToast('info', 'Функция добавления тега в разработке')}
        onStartMailing={handleStartMailing}
      />

      <style>{`
        .cp-page {
          display: flex;
          flex-direction: column;
          height: 100%;
          overflow: hidden;
        }
        .cp-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 24px;
          border-bottom: 1px solid var(--color-border);
          background: var(--color-surface);
          flex-shrink: 0;
          flex-wrap: wrap;
          gap: 8px;
        }
        @media (max-width: 600px) {
          .cp-header { padding: 12px 16px; }
          .cp-title { font-size: 17px; }
        }
        .cp-title {
          font-size: 20px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .cp-count {
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text-secondary);
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 999px;
          padding: 2px 10px;
        }
        .cp-header-actions { display: flex; gap: 8px; }
        .cp-content {
          display: flex;
          flex: 1;
          overflow: hidden;
          background: var(--color-surface);
        }
        .cp-table-area {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .cp-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          border-top: 1px solid var(--color-border);
          flex-shrink: 0;
          background: var(--color-surface);
        }
        .cp-total { font-size: 13px; color: var(--color-text-secondary); }
        .cp-inline-search {
          padding: 10px 16px;
          border-bottom: 1px solid var(--color-border);
          flex-shrink: 0;
        }
        .cp-inline-search-input {
          width: 100%;
          max-width: 320px;
          padding: 7px 12px;
          font-size: 13px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-bg);
          color: var(--color-text);
          outline: none;
          transition: border-color 0.15s;
        }
        .cp-inline-search-input:focus { border-color: var(--color-primary); }
        .cp-inline-search-input::placeholder { color: var(--color-text-secondary); }
        .cp-bulk-select {
          width: 100%;
          padding: 8px 12px;
          font-size: 14px;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-sm);
          background: var(--color-surface);
          color: var(--color-text);
          outline: none;
        }
        .cp-bulk-select:focus {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 3px rgba(59,130,246,.15);
        }
      `}</style>
    </div>
  )
}
