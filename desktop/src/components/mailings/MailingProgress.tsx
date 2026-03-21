import type { MailingJob } from '@/types/mailing'

interface MailingProgressProps {
  job: MailingJob
}

export const MailingProgress = ({ job }: MailingProgressProps) => {
  const percent = job.total > 0 ? Math.round((job.sent / job.total) * 100) : 0

  return (
    <div className="mprog">
      <div className="mprog-bar-wrap">
        <div
          className="mprog-bar-fill"
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      <div className="mprog-stats">
        <span className="mprog-percent">{percent}%</span>
        <span className="mprog-ratio">({job.sent}/{job.total})</span>
      </div>

      <div className="mprog-detail">
        <span className="mprog-sent">
          <span className="mprog-icon mprog-icon--sent">&#10003;</span>
          {job.sent} отправлено
        </span>
        <span className="mprog-failed">
          <span className="mprog-icon mprog-icon--failed">&#10007;</span>
          {job.failed} ошибок
        </span>
        <span className="mprog-skipped">
          <span className="mprog-icon mprog-icon--skip">&#8960;</span>
          {job.skipped} пропущено
        </span>
      </div>

      <style>{`
        .mprog { display: flex; flex-direction: column; gap: 6px; }
        .mprog-bar-wrap {
          height: 8px;
          background: var(--color-border);
          border-radius: 999px;
          overflow: hidden;
        }
        .mprog-bar-fill {
          height: 100%;
          background: var(--color-primary);
          border-radius: 999px;
          transition: width 0.4s ease;
        }
        .mprog-stats {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .mprog-percent { font-size: 14px; font-weight: 600; color: var(--color-text); }
        .mprog-ratio { font-size: 13px; color: var(--color-text-secondary); }
        .mprog-detail {
          display: flex;
          align-items: center;
          gap: 16px;
          flex-wrap: wrap;
        }
        .mprog-sent, .mprog-failed, .mprog-skipped {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 13px;
        }
        .mprog-sent { color: var(--color-success); }
        .mprog-failed { color: var(--color-danger); }
        .mprog-skipped { color: var(--color-text-secondary); }
        .mprog-icon { font-size: 12px; }
      `}</style>
    </div>
  )
}
