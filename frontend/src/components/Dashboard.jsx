import React, { useState, useEffect, useCallback } from 'react'
import KPICards from './KPICards'
import StudentTable from './StudentTable'
import StudentModal from './StudentModal'
import Charts from './Charts'

const API_BASE = '/api'

function Dashboard({ user, department, onLogout, initialData }) {
  const [students, setStudents] = useState(initialData?.students || [])
  const [summary, setSummary] = useState(initialData?.summary || null)
  const [loading, setLoading] = useState(!initialData)
  const [syncing, setSyncing] = useState(false)
  const [loadingFull, setLoadingFull] = useState(initialData?.isQuick || false)
  const [error, setError] = useState(null)
  const [lastSynced, setLastSynced] = useState(initialData ? new Date() : null)
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [showCharts, setShowCharts] = useState(false)

  // Filtering and search
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // Fetch data on mount only if no initial data provided
  useEffect(() => {
    if (!initialData) {
      console.log('[DASHBOARD] Component mounted, fetching data...')
      fetchDashboardData()
    } else {
      console.log('[DASHBOARD] Using pre-fetched data')
      // If we got quick data, load full data in background
      if (initialData.isQuick) {
        console.log('[DASHBOARD] Loading full data in background...')
        loadFullDataInBackground()
      }
    }
  }, [])

  // Load full data with enrollments in background
  const loadFullDataInBackground = async () => {
    try {
      const [summaryRes, studentsRes] = await Promise.all([
        fetch(`${API_BASE}/dashboard/summary`, { credentials: 'include' }),
        fetch(`${API_BASE}/dashboard/students`, { credentials: 'include' })
      ])

      if (summaryRes.ok && studentsRes.ok) {
        const [summaryData, studentsData] = await Promise.all([
          summaryRes.json(),
          studentsRes.json()
        ])

        if (summaryData.success && studentsData.success) {
          console.log('[DASHBOARD] Full data loaded, updating...')
          setSummary(summaryData.summary)
          setStudents(studentsData.students)
          setLastSynced(new Date())
        }
      }
    } catch (err) {
      console.error('[DASHBOARD] Background load failed:', err)
    } finally {
      setLoadingFull(false)
    }
  }

  const fetchDashboardData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      // Fetch summary and students in parallel
      const [summaryRes, studentsRes] = await Promise.all([
        fetch(`${API_BASE}/dashboard/summary`, { credentials: 'include' }),
        fetch(`${API_BASE}/dashboard/students`, { credentials: 'include' })
      ])

      if (!summaryRes.ok || !studentsRes.ok) {
        if (summaryRes.status === 401 || studentsRes.status === 401) {
          onLogout()
          return
        }
        throw new Error('Failed to fetch data')
      }

      const summaryData = await summaryRes.json()
      const studentsData = await studentsRes.json()

      if (summaryData.success) {
        setSummary(summaryData.summary)
      }

      if (studentsData.success) {
        setStudents(studentsData.students)
      }

      setLastSynced(new Date())
    } catch (err) {
      setError('Failed to load dashboard data. Please try again.')
      console.error('Dashboard error:', err)
    } finally {
      setLoading(false)
    }
  }, [onLogout])

  const handleSync = async () => {
    setSyncing(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/dashboard/sync`, {
        method: 'POST',
        credentials: 'include'
      })

      if (!response.ok) {
        if (response.status === 401) {
          onLogout()
          return
        }
        throw new Error('Sync failed')
      }

      const data = await response.json()

      if (data.success) {
        setSummary(data.summary)
        setStudents(data.students)
        setLastSynced(new Date())
      }
    } catch (err) {
      setError('Failed to sync data. Please try again.')
    } finally {
      setSyncing(false)
    }
  }

  const handleExport = async () => {
    try {
      const response = await fetch(`${API_BASE}/dashboard/export`, {
        credentials: 'include'
      })

      if (!response.ok) {
        throw new Error('Export failed')
      }

      // Download the CSV
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `students_export_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      a.remove()
    } catch (err) {
      setError('Failed to export data. Please try again.')
    }
  }

  // Filter students
  const filteredStudents = students.filter(student => {
    // Search filter
    const searchLower = searchTerm.toLowerCase()
    const matchesSearch = !searchTerm ||
      student.fullName.toLowerCase().includes(searchLower) ||
      student.email.toLowerCase().includes(searchLower)

    // Status filter
    const matchesStatus = statusFilter === 'all' ||
      student.status.status.toLowerCase() === statusFilter.toLowerCase()

    return matchesSearch && matchesStatus
  })

  const formatLastSynced = () => {
    if (!lastSynced) return 'Never'

    const now = new Date()
    const diff = Math.floor((now - lastSynced) / 1000)

    if (diff < 60) return 'Just now'
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`
    return lastSynced.toLocaleDateString()
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        {/* Skeleton Header */}
        <header className="header shadow-lg">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="h-10 w-32 bg-white/20 rounded animate-pulse"></div>
                <div>
                  <div className="h-5 w-40 bg-white/20 rounded animate-pulse mb-1"></div>
                  <div className="h-4 w-24 bg-white/10 rounded animate-pulse"></div>
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <div className="h-9 w-20 bg-white/10 rounded-lg animate-pulse"></div>
                <div className="h-9 w-9 bg-white/10 rounded-lg animate-pulse"></div>
              </div>
            </div>
          </div>
        </header>

        {/* Skeleton Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Loading indicator */}
          <div className="text-center mb-6">
            <div className="spinner mx-auto mb-2"></div>
            <p className="text-gray-600 text-sm">Loading student data...</p>
          </div>

          {/* Skeleton KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-white rounded-xl shadow-md p-6 animate-pulse">
                <div className="h-4 w-24 bg-gray-200 rounded mb-3"></div>
                <div className="h-8 w-16 bg-gray-200 rounded"></div>
              </div>
            ))}
          </div>

          {/* Skeleton Table */}
          <div className="bg-white rounded-xl shadow-md overflow-hidden">
            <div className="p-4 border-b">
              <div className="h-10 w-64 bg-gray-200 rounded animate-pulse"></div>
            </div>
            <div className="divide-y">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="p-4 animate-pulse">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="h-10 w-10 bg-gray-200 rounded-full"></div>
                      <div>
                        <div className="h-4 w-32 bg-gray-200 rounded mb-2"></div>
                        <div className="h-3 w-48 bg-gray-100 rounded"></div>
                      </div>
                    </div>
                    <div className="h-6 w-20 bg-gray-200 rounded-full"></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="header shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <img
                src="/logo.png"
                alt="JustInsurance"
                className="h-20 w-auto"
                onError={(e) => { e.target.style.display = 'none' }}
              />
              <div>
                <h1 className="text-xl font-bold text-white">Student Dashboard</h1>
                <p className="text-sm text-ji-blue-light">{department?.name}</p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              {/* Sync Button */}
              <button
                onClick={handleSync}
                disabled={syncing}
                className="flex items-center space-x-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-white transition-colors"
              >
                <svg
                  className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>{syncing ? 'Syncing...' : 'Sync'}</span>
              </button>

              {/* User Menu */}
              <div className="flex items-center space-x-3">
                <div className="text-right hidden sm:block">
                  <p className="text-white font-medium">{user?.name}</p>
                  <p className="text-xs text-ji-blue-light">{user?.email}</p>
                </div>
                <button
                  onClick={onLogout}
                  className="p-2 bg-white/10 hover:bg-white/20 rounded-lg text-white transition-colors"
                  title="Logout"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-red-700">{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Last Synced Info */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <p className="text-sm text-gray-500">
              Last updated: {formatLastSynced()}
            </p>
            {loadingFull && (
              <span className="text-xs text-ji-blue-bright flex items-center gap-1">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                </svg>
                Loading progress data...
              </span>
            )}
          </div>
          <button
            onClick={() => setShowCharts(!showCharts)}
            className="text-sm text-ji-blue-bright hover:text-ji-blue-medium flex items-center space-x-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span>{showCharts ? 'Hide Charts' : 'Show Charts'}</span>
          </button>
        </div>

        {/* KPI Cards */}
        {summary && <KPICards summary={summary} />}

        {/* Charts (collapsible) */}
        {showCharts && summary && (
          <div className="mb-8 animate-fadeIn">
            <Charts summary={summary} students={students} />
          </div>
        )}

        {/* Filters and Search */}
        <div className="bg-white rounded-xl shadow-md p-4 mb-6">
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            {/* Search */}
            <div className="relative flex-1 max-w-md">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </span>
              <input
                type="text"
                placeholder="Search by name or email..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <div className="flex items-center gap-4">
              {/* Status Filter */}
              <select
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="complete">Complete</option>
                <option value="active">Active</option>
                <option value="warning">Warning</option>
                <option value="re-engage">Re-engage</option>
              </select>

              {/* Export Button */}
              <button
                onClick={handleExport}
                className="btn btn-secondary flex items-center space-x-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Export CSV</span>
              </button>
            </div>
          </div>

          {/* Filter Results Count */}
          <div className="mt-3 text-sm text-gray-500">
            Showing {filteredStudents.length} of {students.length} students
          </div>
        </div>

        {/* Student Table */}
        <StudentTable
          students={filteredStudents}
          onViewStudent={setSelectedStudent}
        />
      </main>

      {/* Student Detail Modal */}
      {selectedStudent && (
        <StudentModal
          studentId={selectedStudent.id}
          onClose={() => setSelectedStudent(null)}
          onSessionExpired={onLogout}
        />
      )}
    </div>
  )
}

export default Dashboard
