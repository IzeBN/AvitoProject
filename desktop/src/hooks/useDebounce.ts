import { useState, useEffect } from 'react'

/**
 * Возвращает дебоунсированное значение.
 * Обновляется только после того, как value не менялось `delay` мс.
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}
