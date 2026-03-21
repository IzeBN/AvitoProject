import { Download, FileText } from 'lucide-react'
import { VoicePlayer } from './VoicePlayer'
import type { Message } from '@/types/chat'

interface MessageItemProps {
  message: Message
}

const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

export const MessageItem = ({ message }: MessageItemProps) => {
  const isOutgoing = message.author_type === 'account'
  const isSystem = message.author_type === 'system'

  if (isSystem) {
    return (
      <div className="msg-system">
        <span>{message.content}</span>
        <style>{`
          .msg-system {
            text-align: center;
            padding: 4px 16px;
          }
          .msg-system span {
            display: inline-block;
            padding: 4px 12px;
            background: var(--color-bg);
            border-radius: 999px;
            font-size: 12px;
            color: var(--color-text-secondary);
            border: 1px solid var(--color-border);
          }
        `}</style>
      </div>
    )
  }

  return (
    <div className={`msg-wrap ${isOutgoing ? 'msg-wrap--out' : 'msg-wrap--in'}`}>
      <div className={`msg-bubble ${isOutgoing ? 'msg-bubble--out' : 'msg-bubble--in'}`}>
        {message.message_type === 'text' && (
          <p className="msg-text">{message.content}</p>
        )}

        {message.message_type === 'image' && message.media_url && (
          <div className="msg-image-wrap">
            <img
              src={message.media_url}
              alt="Изображение"
              className="msg-image"
              loading="lazy"
            />
          </div>
        )}

        {message.message_type === 'voice' && message.media_url && (
          <VoicePlayer src={message.media_url} duration={message.duration} />
        )}

        {message.message_type === 'file' && message.media_url && (
          <a
            href={message.media_url}
            target="_blank"
            rel="noopener noreferrer"
            className="msg-file"
            download
          >
            <FileText size={20} className="msg-file-icon" />
            <span className="msg-file-name">{message.content ?? 'Файл'}</span>
            <Download size={14} className="msg-file-dl" />
          </a>
        )}

        <span className="msg-time">{formatTime(message.created_at)}</span>
      </div>

      <style>{`
        .msg-wrap {
          display: flex;
          padding: 2px 16px;
        }
        .msg-wrap--in { justify-content: flex-start; }
        .msg-wrap--out { justify-content: flex-end; }
        .msg-bubble {
          max-width: 65%;
          border-radius: var(--radius-md);
          padding: 8px 12px;
          position: relative;
          word-break: break-word;
        }
        .msg-bubble--in {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-bottom-left-radius: 4px;
        }
        .msg-bubble--out {
          background: var(--color-primary);
          color: #fff;
          border-bottom-right-radius: 4px;
        }
        .msg-text {
          font-size: 14px;
          line-height: 1.5;
          white-space: pre-wrap;
        }
        .msg-time {
          display: block;
          font-size: 11px;
          margin-top: 4px;
          opacity: 0.65;
          text-align: right;
        }
        .msg-image-wrap {
          border-radius: var(--radius-sm);
          overflow: hidden;
          max-width: 240px;
        }
        .msg-image {
          width: 100%;
          display: block;
          cursor: zoom-in;
        }
        .msg-file {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 4px;
          color: inherit;
          text-decoration: none;
        }
        .msg-file-icon { flex-shrink: 0; opacity: 0.7; }
        .msg-file-name {
          flex: 1;
          font-size: 13px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .msg-file-dl { flex-shrink: 0; opacity: 0.6; }
      `}</style>
    </div>
  )
}
