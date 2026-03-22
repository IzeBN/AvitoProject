import { useState, useRef, useCallback, type KeyboardEvent, type ClipboardEvent } from 'react'
import { Paperclip, Zap, Send } from 'lucide-react'
import { FastAnswersPopover } from './FastAnswersPopover'

interface MessageInputProps {
  onSend: (text: string) => void
  onAttachFile?: (file: File) => void
  disabled?: boolean
  sending?: boolean
}

export const MessageInput = ({
  onSend,
  onAttachFile,
  disabled = false,
  sending = false,
}: MessageInputProps) => {
  const [text, setText] = useState('')
  const [fastAnswersOpen, setFastAnswersOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const zapBtnRef = useRef<HTMLButtonElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleInput = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
    setText(ta.value)
  }

  const submit = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || disabled || sending) return
    onSend(trimmed)
    setText('')
    const ta = textareaRef.current
    if (ta) { ta.value = ''; ta.style.height = 'auto' }
  }, [text, disabled, sending, onSend])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const handleFastAnswerSelect = (answer: string) => {
    setText(answer)
    const ta = textareaRef.current
    if (ta) {
      ta.value = answer
      ta.style.height = 'auto'
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
      ta.focus()
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && onAttachFile) onAttachFile(file)
    e.target.value = ''
  }

  const handlePaste = useCallback((e: ClipboardEvent<HTMLDivElement>) => {
    const items = Array.from(e.clipboardData.items)
    const imageItem = items.find(item => item.type.startsWith('image/'))
    if (!imageItem) return
    e.preventDefault()
    const file = imageItem.getAsFile()
    if (file && onAttachFile) {
      onAttachFile(file)
    }
  }, [onAttachFile])

  return (
    <div className="minput-wrap" onPaste={handlePaste}>
      <div className="minput-row">
        {/* Быстрые ответы */}
        <div className="minput-popover-anchor">
          <FastAnswersPopover
            open={fastAnswersOpen}
            onClose={() => setFastAnswersOpen(false)}
            onSelect={handleFastAnswerSelect}
            anchorRef={zapBtnRef}
          />
          <button
            ref={zapBtnRef}
            className={`minput-icon-btn ${fastAnswersOpen ? 'minput-icon-btn--active' : ''}`}
            onClick={() => setFastAnswersOpen(v => !v)}
            disabled={disabled}
            aria-label="Быстрые ответы"
            type="button"
          >
            <Zap size={18} />
          </button>
        </div>

        {/* Прикрепить файл */}
        <button
          className="minput-icon-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          aria-label="Прикрепить файл"
          type="button"
        >
          <Paperclip size={18} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={handleFileChange}
          accept="image/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx"
        />

        {/* Текстовое поле */}
        <textarea
          ref={textareaRef}
          className="minput-textarea"
          placeholder="Напишите сообщение..."
          rows={1}
          onInput={handleInput}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          value={text}
          disabled={disabled}
          aria-label="Поле ввода сообщения"
        />

        {/* Отправить */}
        <button
          className={`minput-send ${text.trim() ? 'minput-send--active' : ''}`}
          onClick={submit}
          disabled={!text.trim() || disabled || sending}
          aria-label="Отправить"
          type="button"
        >
          {sending ? (
            <span className="minput-sending-dot" />
          ) : (
            <Send size={16} />
          )}
        </button>
      </div>

      <style>{`
        .minput-wrap {
          border-top: 1px solid var(--color-border);
          background: var(--color-surface);
          padding: 12px 16px;
        }
        .minput-row {
          display: flex;
          align-items: flex-end;
          gap: 8px;
        }
        .minput-popover-anchor { position: relative; }
        .minput-icon-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: var(--radius-sm);
          color: var(--color-text-secondary);
          flex-shrink: 0;
          transition: background 0.15s, color 0.15s;
        }
        .minput-icon-btn:hover:not(:disabled) {
          background: var(--color-bg);
          color: var(--color-text);
        }
        .minput-icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .minput-icon-btn--active {
          background: #eff6ff;
          color: var(--color-primary);
        }
        .minput-textarea {
          flex: 1;
          min-height: 36px;
          max-height: 160px;
          padding: 8px 12px;
          font-size: 14px;
          line-height: 1.5;
          border: 1px solid var(--color-border);
          border-radius: var(--radius-md);
          background: var(--color-bg);
          color: var(--color-text);
          resize: none;
          outline: none;
          overflow-y: auto;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .minput-textarea:focus {
          border-color: var(--color-primary);
          box-shadow: 0 0 0 3px rgba(59,130,246,.12);
          background: var(--color-surface);
        }
        .minput-textarea::placeholder { color: var(--color-text-secondary); }
        .minput-textarea:disabled { opacity: 0.5; cursor: not-allowed; }
        .minput-send {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: var(--radius-sm);
          background: var(--color-border);
          color: var(--color-text-secondary);
          flex-shrink: 0;
          transition: background 0.15s, color 0.15s;
        }
        .minput-send--active {
          background: var(--color-primary);
          color: #fff;
        }
        .minput-send--active:hover:not(:disabled) { background: var(--color-primary-hover); }
        .minput-send:disabled { opacity: 0.6; cursor: not-allowed; }
        .minput-sending-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: currentColor;
          animation: pulseDot 0.8s ease infinite alternate;
        }
        @keyframes pulseDot { from { opacity: 0.4; } to { opacity: 1; } }
      `}</style>
    </div>
  )
}
