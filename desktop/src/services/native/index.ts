/**
 * Автоматически выбирает реализацию в зависимости от среды.
 * В Tauri окружении используется нативный слой (keychain, уведомления ОС).
 * В браузере — fallback на localStorage и Web Notifications API.
 */
import type { NativeService } from './tauri'
import { tauriNative } from './tauri'
import { webNative } from './web'

const isTauri =
  typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export const native: NativeService = isTauri ? tauriNative : webNative
