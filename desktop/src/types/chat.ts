export type MessageAuthorType = 'account' | 'candidate' | 'system'
export type MessageContentType = 'text' | 'image' | 'voice' | 'file' | 'system'

export interface Message {
  id: string
  chat_id: string
  author_type: MessageAuthorType
  message_type: MessageContentType
  content: string | null
  /** URL для медиафайлов (image, voice, file) */
  media_url?: string | null
  /** Длительность голосового сообщения в секундах */
  duration?: number | null
  is_read: boolean
  created_at: string
}

export interface ChatListItem {
  candidate_id: string
  candidate_name: string | null
  chat_id: string
  last_message: string | null
  last_message_at: string | null
  unread_count: number
  is_blocked: boolean
}
