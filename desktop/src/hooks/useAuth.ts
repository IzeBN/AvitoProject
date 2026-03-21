import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth.store'

export function useLogin() {
  const setTokens = useAuthStore(s => s.setTokens)
  const navigate = useNavigate()

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      authApi.login(email, password),
    onSuccess: async (data) => {
      await setTokens(data.access_token, data.refresh_token)
      navigate('/candidates', { replace: true })
    },
  })
}

export function useRegister() {
  const setTokens = useAuthStore(s => s.setTokens)
  const navigate = useNavigate()

  return useMutation({
    mutationFn: (data: { email: string; username: string; full_name: string; password: string }) =>
      authApi.register(data),
    onSuccess: async (data) => {
      await setTokens(data.access_token, data.refresh_token)
      // После регистрации орги нет — OrgGuard покажет NoOrgPage
      navigate('/', { replace: true })
    },
  })
}

export function useLogout() {
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()

  return async () => {
    await logout()
    navigate('/login', { replace: true })
  }
}
