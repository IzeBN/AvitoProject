export interface Candidate {
  id: string
  name: string | null
  phone: string | null
  vacancy: string | null
  vacancy_id: string | null
  location: string | null
  stage: { id: string; name: string; color: string | null } | null
  department: { id: string; name: string } | null
  responsible: { id: string; full_name: string } | null
  tags: Array<{ id: string; name: string; color: string | null }>
  comment: string | null
  due_date: string | null
  has_new_message: boolean
  last_message: string | null
  last_message_at: string | null
  unread_count: number
  source: string | null
  created_at: string
  updated_at: string
}

export interface CandidateFilters {
  stage_id?: string
  responsible_id?: string
  department_id?: string
  avito_account_id?: string
  tag_ids?: string[]
  has_new_message?: boolean
  only_unread?: boolean
  search?: string
  location?: string
  vacancy?: string
  due_date_from?: string
  due_date_to?: string
  created_at_from?: string
  created_at_to?: string
}
