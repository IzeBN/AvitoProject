import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLogin } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Mail, Lock } from 'lucide-react'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [formErrors, setFormErrors] = useState({ email: '', password: '' })

  const login = useLogin()

  const validate = (): boolean => {
    const errors = { email: '', password: '' }
    if (!email.trim()) {
      errors.email = 'Введите email'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Некорректный email'
    }
    if (!password) {
      errors.password = 'Введите пароль'
    } else if (password.length < 6) {
      errors.password = 'Минимум 6 символов'
    }
    setFormErrors(errors)
    return !errors.email && !errors.password
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    login.mutate({ email: email.trim(), password })
  }

  const serverError =
    login.error instanceof Error
      ? login.error.message
      : login.isError
        ? 'Неверный email или пароль'
        : null

  return (
    <div className="login-page">
      <div className="login-card">
        {/* Заголовок */}
        <div className="login-header">
          <div className="login-logo">A</div>
          <h1 className="login-title">AvitoСRM</h1>
          <p className="login-subtitle">Войдите в свой аккаунт</p>
        </div>

        {/* Форма */}
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <Input
            type="email"
            label="Email"
            placeholder="you@company.ru"
            value={email}
            onChange={e => {
              setEmail(e.target.value)
              if (formErrors.email) setFormErrors(p => ({ ...p, email: '' }))
            }}
            error={formErrors.email}
            leftIcon={<Mail size={15} />}
            autoComplete="email"
            autoFocus
          />

          <Input
            type="password"
            label="Пароль"
            placeholder="••••••••"
            value={password}
            onChange={e => {
              setPassword(e.target.value)
              if (formErrors.password) setFormErrors(p => ({ ...p, password: '' }))
            }}
            error={formErrors.password}
            leftIcon={<Lock size={15} />}
            autoComplete="current-password"
          />

          {/* Ошибка сервера */}
          {serverError && (
            <div className="login-server-error" role="alert">
              {serverError}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={login.isPending}
            className="login-submit"
          >
            Войти
          </Button>
        </form>

        <p className="login-register-link">
          Нет аккаунта?{' '}
          <button
            type="button"
            className="login-link-btn"
            onClick={() => navigate('/register')}
          >
            Зарегистрировать организацию
          </button>
        </p>
      </div>

      <style>{`
        .login-page {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }
        .login-card {
          width: 100%;
          max-width: 400px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: 40px 36px;
          box-shadow: var(--shadow-md);
        }
        .login-header {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin-bottom: 32px;
        }
        .login-logo {
          width: 52px;
          height: 52px;
          border-radius: 14px;
          background: var(--color-primary);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 22px;
          font-weight: 800;
          margin-bottom: 12px;
        }
        .login-title {
          font-size: 22px;
          font-weight: 700;
          color: var(--color-text);
          margin-bottom: 4px;
        }
        .login-subtitle {
          font-size: 14px;
          color: var(--color-text-secondary);
        }
        .login-form {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .login-server-error {
          padding: 10px 14px;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: var(--radius-sm);
          font-size: 13px;
          color: var(--color-danger);
        }
        .login-submit { width: 100%; }
        .login-register-link {
          text-align: center;
          font-size: 13px;
          color: var(--color-text-secondary);
          margin: 16px 0 0;
        }
        .login-link-btn {
          background: none;
          border: none;
          padding: 0;
          color: var(--color-primary);
          cursor: pointer;
          font-size: 13px;
          font-weight: 500;
        }
        .login-link-btn:hover { text-decoration: underline; }
      `}</style>
    </div>
  )
}
