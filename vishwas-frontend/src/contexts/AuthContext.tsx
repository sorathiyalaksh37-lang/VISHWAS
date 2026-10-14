import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { apiClient } from '../services/api'

interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
}

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>
  register: (email: string, password: string, fullName?: string) => Promise<{ success: boolean; error?: string }>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const TOKEN_KEY = 'vishwas:auth_token'
const USER_KEY = 'vishwas:user'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Load token and user from localStorage on mount
  useEffect(() => {
    async function initAuth() {
      const storedToken = localStorage.getItem(TOKEN_KEY)
      const storedUser = localStorage.getItem(USER_KEY)

      if (storedToken && storedUser) {
        try {
          const parsedUser = JSON.parse(storedUser) as User
          setToken(storedToken)
          setUser(parsedUser)
          
          // Verify token is still valid
          const userData = await apiClient.getCurrentUser()
          if (userData) {
            setUser(userData)
            localStorage.setItem(USER_KEY, JSON.stringify(userData))
          } else {
            // Token is invalid, try auto-login with demo user
            console.log('[Auth] Token invalid, attempting auto-login with demo user')
            await autoLogin()
          }
        } catch {
          // Invalid stored data, try auto-login
          await autoLogin()
        }
      } else {
        // No credentials stored, auto-login with demo user
        console.log('[Auth] No stored credentials, attempting auto-login')
        await autoLogin()
      }
      
      setIsLoading(false)
    }

    async function autoLogin() {
      try {
        console.log('[Auth] Auto-logging in with Shubham21@gmail.com...')
        const response = await apiClient.login('Shubham21@gmail.com', 'Shubham')
        
        if (response) {
          const { access_token, user: userData } = response
          setToken(access_token)
          setUser(userData)
          localStorage.setItem(TOKEN_KEY, access_token)
          localStorage.setItem(USER_KEY, JSON.stringify(userData))
          console.log('[Auth] ✓ Auto-login successful')
        } else {
          console.error('[Auth] Auto-login failed')
        }
      } catch (error) {
        console.error('[Auth] Auto-login error:', error)
      }
    }

    initAuth()
  }, [])

  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await apiClient.login(email, password)
      
      if (response) {
        const { access_token, user: userData } = response
        setToken(access_token)
        setUser(userData)
        localStorage.setItem(TOKEN_KEY, access_token)
        localStorage.setItem(USER_KEY, JSON.stringify(userData))
        return { success: true }
      }
      
      return { success: false, error: 'Invalid credentials' }
    } catch (error) {
      console.error('Login error:', error)
      return { success: false, error: error instanceof Error ? error.message : 'Login failed' }
    }
  }

  const register = async (email: string, password: string, fullName?: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await apiClient.register(email, password, fullName)
      
      if (response) {
        const { access_token, user: userData } = response
        setToken(access_token)
        setUser(userData)
        localStorage.setItem(TOKEN_KEY, access_token)
        localStorage.setItem(USER_KEY, JSON.stringify(userData))
        return { success: true }
      }
      
      return { success: false, error: 'Registration failed' }
    } catch (error) {
      console.error('Register error:', error)
      return { success: false, error: error instanceof Error ? error.message : 'Registration failed' }
    }
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
