import clsx from 'clsx'

type SpinnerSize = 'sm' | 'md' | 'lg'

interface SpinnerProps {
  size?: SpinnerSize
  className?: string
}

const sizeMap: Record<SpinnerSize, number> = {
  sm: 14,
  md: 20,
  lg: 32,
}

export const Spinner = ({ size = 'md', className }: SpinnerProps) => {
  const px = sizeMap[size]
  return (
    <span
      role="status"
      aria-label="Загрузка"
      className={clsx('spinner', className)}
      style={{ width: px, height: px }}
    >
      <style>{`
        .spinner {
          display: inline-block;
          border-radius: 50%;
          border: 2px solid var(--color-border);
          border-top-color: var(--color-primary);
          animation: spin 0.7s linear infinite;
          flex-shrink: 0;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </span>
  )
}
