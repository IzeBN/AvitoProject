import React, { Suspense, useEffect } from 'react'
import { MemoryRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth.store'
import { NoOrgPage } from '@/pages/NoOrgPage/NoOrgPage'

import AppLayout from '@/components/layout/AppLayout'
import AuthLayout from '@/components/layout/AuthLayout'

const LoginPage        = React.lazy(() => import('@/pages/LoginPage/LoginPage'))
const RegisterPage     = React.lazy(() => import('@/pages/RegisterPage/RegisterPage'))
const CandidatesPage   = React.lazy(() => import('@/pages/CandidatesPage/CandidatesPage'))
const MessengerPage    = React.lazy(() => import('@/pages/MessengerPage/MessengerPage'))
const MailingsPage     = React.lazy(() => import('@/pages/MailingsPage/MailingsPage'))
const TasksPage        = React.lazy(() => import('@/pages/TasksPage/TasksPage'))
const AnalyticsPage    = React.lazy(() => import('@/pages/AnalyticsPage/AnalyticsPage'))
const VacanciesPage    = React.lazy(() => import('@/pages/VacanciesPage/VacanciesPage'))
const AvitoAccountsPage = React.lazy(() => import('@/pages/AvitoAccountsPage/AvitoAccountsPage'))
const AutoResponsePage = React.lazy(() => import('@/pages/AutoResponsePage/AutoResponsePage'))
const SelfEmployedPage = React.lazy(() => import('@/pages/SelfEmployedPage/SelfEmployedPage'))
const UsersPage        = React.lazy(() => import('@/pages/UsersPage/UsersPage'))
const SettingsPage     = React.lazy(() => import('@/pages/SettingsPage/SettingsPage'))
const SuperAdminPage   = React.lazy(() => import('@/pages/SuperAdminPage/SuperAdminPage'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      gcTime: 1000 * 60 * 5,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const Splash = () => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '100vh', background: 'var(--color-bg)',
    color: 'var(--color-text-secondary)', fontSize: 14,
  }}>
    Загрузка...
  </div>
)

const PageFallback = () => (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '100%', color: 'var(--color-text-secondary)', fontSize: 14,
  }}>
    Загрузка...
  </div>
)

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.accessToken)
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function OrgGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore(s => s.user)
  if (user?.role === 'superadmin') return <>{children}</>
  if (!user?.org_id) return <Navigate to="/no-org" replace />
  return <>{children}</>
}

function AppRoutes() {
  const initializing = useAuthStore(s => s.initializing)
  const accessToken  = useAuthStore(s => s.accessToken)

  // Показываем Splash только при холодном старте (нет токена, ещё грузимся)
  if (initializing && !accessToken) return <Splash />

  return (
    <Routes>
      <Route element={<Suspense fallback={<PageFallback />}><AuthLayout /></Suspense>}>
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Страница без организации */}
      <Route
        path="/no-org"
        element={
          <PrivateRoute>
            <NoOrgPage reason="no_org" />
          </PrivateRoute>
        }
      />

      {/* Основное приложение — Suspense живёт внутри AppLayout вокруг Outlet */}
      <Route
        element={
          <PrivateRoute>
            <OrgGuard>
              <AppLayout />
            </OrgGuard>
          </PrivateRoute>
        }
      >
        <Route path="/"                        element={<Navigate to="/candidates" replace />} />
        <Route path="/candidates"              element={<CandidatesPage />} />
        <Route path="/messenger"               element={<MessengerPage />} />
        <Route path="/messenger/:candidateId"  element={<MessengerPage />} />
        <Route path="/mailings"                element={<MailingsPage />} />
        <Route path="/tasks"                   element={<TasksPage />} />
        <Route path="/analytics"               element={<AnalyticsPage />} />
        <Route path="/vacancies"               element={<VacanciesPage />} />
        <Route path="/avito-accounts"          element={<AvitoAccountsPage />} />
        <Route path="/auto-response"           element={<AutoResponsePage />} />
        <Route path="/self-employed"           element={<SelfEmployedPage />} />
        <Route path="/users"                   element={<UsersPage />} />
        <Route path="/settings/*"              element={<SettingsPage />} />
        <Route path="/superadmin"              element={<SuperAdminPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function AuthInitializer({ children }: { children: React.ReactNode }) {
  const loadFromStorage = useAuthStore(s => s.loadFromStorage)

  useEffect(() => {
    void loadFromStorage()
  }, [loadFromStorage])

  return <>{children}</>
}

const LAST_PATH_KEY = 'app_last_path'
const PROTECTED_PATHS = [
  '/candidates', '/messenger', '/mailings', '/tasks', '/analytics',
  '/vacancies', '/avito-accounts', '/auto-response', '/self-employed',
  '/users', '/settings', '/superadmin',
]

function PathPersistor() {
  const location = useLocation()

  useEffect(() => {
    const path = location.pathname
    if (PROTECTED_PATHS.some(p => path === p || path.startsWith(p + '/'))) {
      localStorage.setItem(LAST_PATH_KEY, path + location.search)
    }
  }, [location])

  return null
}

function getInitialPath(): string {
  const saved = localStorage.getItem(LAST_PATH_KEY)
  if (saved && PROTECTED_PATHS.some(p => saved === p || saved.startsWith(p + '/') || saved.startsWith(p + '?'))) {
    return saved
  }
  return '/'
}

export const App = () => {
  const initialPath = getInitialPath()

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]} initialIndex={0}>
        <AuthInitializer>
          <PathPersistor />
          <AppRoutes />
        </AuthInitializer>
      </MemoryRouter>
    </QueryClientProvider>
  )
}
