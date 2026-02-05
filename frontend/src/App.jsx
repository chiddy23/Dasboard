import React, { useState, useEffect } from 'react'
import Login from './components/Login'
import Dashboard from './components/Dashboard'

// API base URL - uses proxy in development
const API_BASE = '/api'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [department, setDepartment] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [preparingDashboard, setPreparingDashboard] = useState(false)
  const [initialData, setInitialData] = useState(null)

  // Check for existing session on mount
  useEffect(() => {
    checkSession()
  }, [])

  const checkSession = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/session`, {
        credentials: 'include'
      })

      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          setUser(data.user)
          setDepartment(data.department)
          setIsAuthenticated(true)
        }
      }
    } catch (err) {
      console.log('No existing session')
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async (credentials) => {
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify(credentials)
      })

      const data = await response.json()

      if (response.ok && data.success) {
        console.log('[APP] Login successful, pre-fetching dashboard data...')
        setUser(data.user)
        setDepartment(data.department)
        setPreparingDashboard(true)

        // Skip pre-fetch - let Dashboard handle data loading
        // This avoids race conditions with session establishment
        console.log('[APP] Skipping pre-fetch, Dashboard will load data')

        setPreparingDashboard(false)
        setIsAuthenticated(true)
        return { success: true }
      } else {
        const errorMsg = data.error || 'Login failed'
        setError(errorMsg)
        return { success: false, error: errorMsg }
      }
    } catch (err) {
      const errorMsg = 'Unable to connect to server. Please try again.'
      setError(errorMsg)
      return { success: false, error: errorMsg }
    }
  }

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      })
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      setUser(null)
      setDepartment(null)
      setIsAuthenticated(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center login-bg">
        <div className="text-center">
          <div className="spinner mx-auto mb-4" style={{ borderTopColor: '#63b3ed' }}></div>
          <p className="text-white text-lg">Loading...</p>
        </div>
      </div>
    )
  }

  if (preparingDashboard) {
    return (
      <div className="min-h-screen flex items-center justify-center login-bg">
        <div className="text-center max-w-md px-6">
          <div className="spinner mx-auto mb-4" style={{ borderTopColor: '#63b3ed' }}></div>
          <p className="text-white text-xl font-semibold mb-2">Welcome, {user?.name}!</p>
          <p className="text-ji-blue-light">Loading your dashboard...</p>
          <p className="text-ji-blue-light text-sm mt-2 opacity-75">Fetching student data from Absorb LMS</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} error={error} />
  }

  return (
    <Dashboard
      user={user}
      department={department}
      onLogout={handleLogout}
      initialData={initialData}
    />
  )
}

export default App
