import { Suspense, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { ToastContainer } from '@/components/ui/Toast'
import { useAuthStore } from '@/stores/auth.store'
import { wsManager } from '@/api/websocket'
import { initWebSocketHandlers } from '@/stores/ws.store'

const ContentFallback = () => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '100%', color: 'var(--color-text-secondary)', fontSize: 14,
  }}>
    Загрузка...
  </div>
)

export default function AppLayout() {
  const accessToken = useAuthStore(s => s.accessToken)
  const queryClient = useQueryClient()

  // Инициализируем WebSocket после получения токена
  useEffect(() => {
    if (!accessToken) return
    wsManager.connect()
    const cleanup = initWebSocketHandlers(queryClient)
    return () => {
      cleanup()
      wsManager.disconnect()
    }
  }, [accessToken, queryClient])

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-main">
        <Header />
        <main className="app-content">
          <Suspense fallback={<ContentFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <ToastContainer />

      <style>{`
        .app-layout {
          display: flex;
          height: 100vh;
          overflow: hidden;
        }
        .app-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-width: 0;
        }
        .app-content {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
        }
        /* Responsive: auto-collapse sidebar on narrow screens */
        @media (max-width: 768px) {
          .app-layout { position: relative; }
        }
      `}</style>
    </div>
  )
}
