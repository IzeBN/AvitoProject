/** Общие типы API */

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  pages: number
  page: number
  page_size: number
}

export interface ApiError {
  detail: string
  code?: string
}
