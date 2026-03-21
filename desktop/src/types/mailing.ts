export type MailingStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'resuming'
  | 'stopping'
  | 'done'
  | 'failed'
  | 'cancelled'

export interface MailingJob {
  id: string
  status: MailingStatus
  message: string
  total: number
  sent: number
  failed: number
  skipped: number
  scheduled_at: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  created_by: { id: string; full_name: string }
}
