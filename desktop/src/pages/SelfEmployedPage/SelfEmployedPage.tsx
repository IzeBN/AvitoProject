import { useState, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  selfEmployedApi,
  type SelfEmployedCheckResult,
  type SelfEmployedHistoryEntry,
} from '@/api/self-employed'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { Pagination } from '@/components/ui/Pagination'
import { useUIStore } from '@/stores/ui.store'
import { Search, Upload, CheckCircle, XCircle } from 'lucide-react'

function parseCsvInns(text: string): string[] {
  return text
    .split(/[\n,;]+/)
    .map(s => s.trim())
    .filter(s => /^\d{10,12}$/.test(s))
}

export default function SelfEmployedPage() {
  const showToast = useUIStore(s => s.showToast)

  const [inn, setInn] = useState('')
  const [lastResult, setLastResult] = useState<SelfEmployedCheckResult | null>(null)
  const [bulkResults, setBulkResults] = useState<SelfEmployedCheckResult[] | null>(null)
  const [historyPage, setHistoryPage] = useState(1)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['self-employed', 'history', historyPage],
    queryFn: () => selfEmployedApi.getHistory(historyPage),
    staleTime: 30_000,
  })

  const checkMutation = useMutation({
    mutationFn: (val: string) => selfEmployedApi.check(val),
    onSuccess: data => {
      setLastResult(data)
      setBulkResults(null)
      setHistoryPage(1)
    },
    onError: () => showToast('error', 'Не удалось проверить ИНН'),
  })

  const checkBulkMutation = useMutation({
    mutationFn: (inns: string[]) => selfEmployedApi.checkBulk(inns),
    onSuccess: data => {
      setBulkResults(data)
      setLastResult(null)
      setHistoryPage(1)
    },
    onError: () => showToast('error', 'Не удалось выполнить массовую проверку'),
  })

  const handleCheck = () => {
    const trimmed = inn.trim()
    if (!/^\d{10,12}$/.test(trimmed)) {
      showToast('warning', 'Введите корректный ИНН (10 или 12 цифр)')
      return
    }
    checkMutation.mutate(trimmed)
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const text = ev.target?.result as string
      const inns = parseCsvInns(text)
      if (!inns.length) {
        showToast('warning', 'Не найдено корректных ИНН в файле')
        return
      }
      checkBulkMutation.mutate(inns)
    }
    reader.readAsText(file)
    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const historyItems = historyData?.items ?? []
  const totalPages = historyData?.total_pages ?? 1

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700 }}>Проверка самозанятых</h1>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* Left panel */}
        <div
          style={{
            flex: '0 0 320px',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              padding: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 600 }}>Проверить ИНН</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={inn}
                onChange={e => setInn(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleCheck()
                }}
                placeholder="771234567890"
                maxLength={12}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  fontSize: 14,
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-surface)',
                  color: 'var(--color-text)',
                  outline: 'none',
                  fontFamily: 'inherit',
                }}
              />
              <Button
                icon={<Search size={14} />}
                loading={checkMutation.isPending}
                onClick={handleCheck}
                disabled={!inn.trim()}
              >
                OK
              </Button>
            </div>

            <div
              style={{
                borderTop: '1px solid var(--color-border)',
                paddingTop: 12,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                Или загрузите CSV / TXT файл со списком ИНН
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.txt"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
              />
              <Button
                variant="secondary"
                icon={<Upload size={14} />}
                loading={checkBulkMutation.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                Загрузить файл
              </Button>
            </div>
          </div>

          {/* Single result */}
          {lastResult && (
            <div
              style={{
                background: 'var(--color-surface)',
                border: `1px solid ${lastResult.is_active ? '#bbf7d0' : 'var(--color-border)'}`,
                borderRadius: 'var(--radius-md)',
                padding: '16px 20px',
              }}
            >
              <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
                Результат проверки
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {lastResult.is_active ? (
                  <CheckCircle size={20} color="var(--color-success)" />
                ) : (
                  <XCircle size={20} color="var(--color-danger)" />
                )}
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>
                    ИНН {lastResult.inn}
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      color: lastResult.is_active
                        ? 'var(--color-success)'
                        : 'var(--color-danger)',
                    }}
                  >
                    {lastResult.is_active ? 'Самозанятый активен' : 'Не является самозанятым'}
                  </div>
                  {lastResult.registration_date && (
                    <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 2 }}>
                      Зарегистрирован:{' '}
                      {new Date(lastResult.registration_date).toLocaleDateString('ru-RU')}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Bulk results */}
          {bulkResults && (
            <div
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                padding: '16px 20px',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
                Результаты массовой проверки ({bulkResults.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 280, overflowY: 'auto' }}>
                {bulkResults.map(r => (
                  <div
                    key={r.inn}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}
                  >
                    {r.is_active ? (
                      <CheckCircle size={14} color="var(--color-success)" />
                    ) : (
                      <XCircle size={14} color="var(--color-danger)" />
                    )}
                    <span style={{ fontFamily: 'monospace' }}>{r.inn}</span>
                    <Badge variant={r.is_active ? 'success' : 'danger'}>
                      {r.is_active ? 'активен' : 'неактивен'}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right panel — history */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>История проверок</div>

          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
            }}
          >
            {historyLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
                <Spinner />
              </div>
            ) : !historyItems.length ? (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: 14 }}>
                История проверок пуста
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--color-bg)', borderBottom: '1px solid var(--color-border)' }}>
                    {['ИНН', 'Статус', 'Дата', 'Проверил'].map(h => (
                      <th
                        key={h}
                        style={{
                          padding: '9px 14px',
                          textAlign: 'left',
                          fontSize: 11,
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {historyItems.map((entry: SelfEmployedHistoryEntry, i: number) => (
                    <tr
                      key={entry.id}
                      style={{
                        borderBottom:
                          i < historyItems.length - 1 ? '1px solid var(--color-border)' : 'none',
                      }}
                    >
                      <td style={{ padding: '10px 14px', fontFamily: 'monospace' }}>
                        {entry.inn}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          {entry.is_active ? (
                            <CheckCircle size={14} color="var(--color-success)" />
                          ) : (
                            <XCircle size={14} color="var(--color-danger)" />
                          )}
                          <Badge variant={entry.is_active ? 'success' : 'danger'}>
                            {entry.is_active ? 'активен' : 'неактивен'}
                          </Badge>
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--color-text-secondary)' }}>
                        {new Date(entry.checked_at).toLocaleString('ru-RU')}
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--color-text-secondary)' }}>
                        {entry.checked_by ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <Pagination
                page={historyPage}
                totalPages={totalPages}
                onPageChange={setHistoryPage}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
