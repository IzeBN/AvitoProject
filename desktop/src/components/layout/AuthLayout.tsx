import { Outlet, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth.store'

export default function AuthLayout() {
  const token = useAuthStore(s => s.accessToken)
  if (token) return <Navigate to="/candidates" replace />

  return (
    <div className="auth-layout">
      <Outlet />
      <style>{`
        .auth-layout {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--color-bg);
        }
      `}</style>
    </div>
  )
}
