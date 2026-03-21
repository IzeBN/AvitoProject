import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { useRegister } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { User, Mail, AtSign, Lock } from 'lucide-react'

type FormFields = {
  full_name: string
  email: string
  username: string
  password: string
  confirmPassword: string
}

type FormErrors = Record<keyof FormFields, string>

const EMPTY_ERRORS: FormErrors = {
  full_name: '',
  email: '',
  username: '',
  password: '',
  confirmPassword: '',
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const register = useRegister()

  const [fields, setFields] = useState<FormFields>({
    full_name: '',
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
  })
  const [formErrors, setFormErrors] = useState<FormErrors>(EMPTY_ERRORS)

  const setField = (key: keyof FormFields) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = key === 'username' ? e.target.value.toLowerCase() : e.target.value
    setFields(prev => ({ ...prev, [key]: value }))
    if (formErrors[key]) setFormErrors(prev => ({ ...prev, [key]: '' }))
  }

  const validate = (): boolean => {
    const errors = { ...EMPTY_ERRORS }

    if (!fields.full_name.trim()) errors.full_name = 'Введите полное имя'

    if (!fields.email.trim()) {
      errors.email = 'Введите email'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) {
      errors.email = 'Некорректный email'
    }

    if (!fields.username.trim()) {
      errors.username = 'Введите имя пользователя'
    } else if (fields.username.length < 3) {
      errors.username = 'Минимум 3 символа'
    } else if (!/^[a-z0-9_]+$/.test(fields.username)) {
      errors.username = 'Только латинские буквы, цифры и _'
    }

    if (!fields.password) {
      errors.password = 'Введите пароль'
    } else if (fields.password.length < 8) {
      errors.password = 'Минимум 8 символов'
    } else if (!/[A-Z]/.test(fields.password)) {
      errors.password = 'Минимум одна заглавная буква'
    } else if (!/[0-9]/.test(fields.password)) {
      errors.password = 'Минимум одна цифра'
    }

    if (!fields.confirmPassword) {
      errors.confirmPassword = 'Подтвердите пароль'
    } else if (fields.password !== fields.confirmPassword) {
      errors.confirmPassword = 'Пароли не совпадают'
    }

    setFormErrors(errors)
    return Object.values(errors).every(e => !e)
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    register.mutate({
      full_name: fields.full_name.trim(),
      email: fields.email.trim(),
      username: fields.username.trim(),
      password: fields.password,
    })
  }

  const serverError = register.isError
    ? (axios.isAxiosError(register.error) && register.error.response?.data?.detail)
      || 'Ошибка регистрации. Проверьте данные и попробуйте снова.'
    : null

  return (
    <div className="reg-page">
      <div className="reg-card">
        <div className="reg-header">
          <div className="reg-logo">A</div>
          <h1 className="reg-title">Регистрация</h1>
          <p className="reg-subtitle">Создайте личный аккаунт</p>
        </div>

        <form className="reg-form" onSubmit={handleSubmit} noValidate>
          <Input
            label="Полное имя"
            placeholder="Иван Иванов"
            value={fields.full_name}
            onChange={setField('full_name')}
            error={formErrors.full_name}
            leftIcon={<User size={15} />}
            autoComplete="name"
            autoFocus
          />

          <Input
            type="email"
            label="Email"
            placeholder="you@company.ru"
            value={fields.email}
            onChange={setField('email')}
            error={formErrors.email}
            leftIcon={<Mail size={15} />}
            autoComplete="email"
          />

          <Input
            label="Имя пользователя"
            placeholder="ivan_ivanov"
            value={fields.username}
            onChange={setField('username')}
            error={formErrors.username}
            leftIcon={<AtSign size={15} />}
            autoComplete="username"
            hint="Только латинские буквы, цифры и _"
          />

          <Input
            type="password"
            label="Пароль"
            placeholder="••••••••"
            value={fields.password}
            onChange={setField('password')}
            error={formErrors.password}
            leftIcon={<Lock size={15} />}
            autoComplete="new-password"
            hint="Минимум 8 символов, заглавная буква и цифра"
          />

          <Input
            type="password"
            label="Подтвердить пароль"
            placeholder="••••••••"
            value={fields.confirmPassword}
            onChange={setField('confirmPassword')}
            error={formErrors.confirmPassword}
            leftIcon={<Lock size={15} />}
            autoComplete="new-password"
          />

          {serverError && (
            <div className="reg-server-error" role="alert">
              {serverError}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={register.isPending}
            className="reg-submit"
          >
            Зарегистрироваться
          </Button>
        </form>

        <p className="reg-login-link">
          Уже есть аккаунт?{' '}
          <button
            type="button"
            className="reg-link-btn"
            onClick={() => navigate('/login')}
          >
            Войти
          </button>
        </p>
      </div>

      <style>{`
        .reg-page {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }
        .reg-card {
          width: 100%;
          max-width: 400px;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-lg);
          padding: 40px 36px;
          box-shadow: var(--shadow-md);
        }
        .reg-header {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin-bottom: 32px;
        }
        .reg-logo {
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
        .reg-title {
          font-size: 22px;
          font-weight: 700;
          color: var(--color-text);
          margin-bottom: 4px;
        }
        .reg-subtitle {
          font-size: 14px;
          color: var(--color-text-secondary);
        }
        .reg-form {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .reg-server-error {
          padding: 10px 14px;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: var(--radius-sm);
          font-size: 13px;
          color: var(--color-danger);
        }
        .reg-submit { width: 100%; }
        .reg-login-link {
          text-align: center;
          font-size: 13px;
          color: var(--color-text-secondary);
          margin: 16px 0 0;
        }
        .reg-link-btn {
          background: none;
          border: none;
          padding: 0;
          color: var(--color-primary);
          cursor: pointer;
          font-size: 13px;
          font-weight: 500;
        }
        .reg-link-btn:hover { text-decoration: underline; }
      `}</style>
    </div>
  )
}
