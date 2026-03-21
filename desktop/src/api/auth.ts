import { apiClient } from './client'

interface TokensResponse {
  access_token: string
  refresh_token: string
}

interface RegisterPayload {
  email: string
  username: string
  full_name: string
  password: string
}

export const authApi = {
  login: (email: string, password: string) =>
    apiClient
      .post<TokensResponse>('/auth/login', { email, password })
      .then(r => r.data),

  register: (data: RegisterPayload) =>
    apiClient
      .post<TokensResponse>('/auth/register', data)
      .then(r => r.data),

  me: () => apiClient.get('/auth/me').then(r => r.data),

  logout: (refreshToken: string) =>
    apiClient.post('/auth/logout', { refresh_token: refreshToken }),
}
