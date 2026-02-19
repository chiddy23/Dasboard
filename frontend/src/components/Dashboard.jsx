import React, { useState, useEffect, useCallback } from 'react'
import KPICards from './KPICards'
import StudentTable from './StudentTable'
import ExamTable from './ExamTable'
import StudentModal from './StudentModal'
import ExamSheetModal from './ExamSheetModal'
import Charts from './Charts'
import ExamCharts from './ExamCharts'

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
  const [showExamCharts, setShowExamCharts] = useState(false)

  // Tab state
  const [activeTab, setActiveTab] = useState('students')
  const [examStudents, setExamStudents] = useState([])
  const [examSummary, setExamSummary] = useState(null)
  const [examLoading, setExamLoading] = useState(false)
  const [examLoaded, setExamLoaded] = useState(false)

  // Admin mode
  const [adminMode, setAdminMode] = useState(false)
  const [adminKey, setAdminKey] = useState('')
  const [showAdminInput, setShowAdminInput] = useState(false)
  const [adminError, setAdminError] = useState('')

  // Scheduler info
  const [schedulerInfo, setSchedulerInfo] = useState(null)

  // Multi-department state
  const [extraDepartments, setExtraDepartments] = useState(() => {
    try {
      const saved = localStorage.getItem('ji_extra_departments')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [showDeptManager, setShowDeptManager] = useState(false)
  const [deptInputValue, setDeptInputValue] = useState('')
  const [deptError, setDeptError] = useState('')
  const [departmentMeta, setDepartmentMeta] = useState([])
  const [studentDeptFilter, setStudentDeptFilter] = useState([])
  const [showDeptDropdown, setShowDeptDropdown] = useState(false)

  // Filtering and search
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [examResultFilter, setExamResultFilter] = useState('no-result')
  const [examCourseFilter, setExamCourseFilter] = useState('all')
  const [examDeptFilter, setExamDeptFilter] = useState([])
  const [showExamDeptDropdown, setShowExamDeptDropdown] = useState(false)
  const [examStateFilter, setExamStateFilter] = useState('all')
  const [examReadinessFilter, setExamReadinessFilter] = useState('all')
  const [examDaysFilter, setExamDaysFilter] = useState('all')

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

  // Persist extra departments to localStorage
  useEffect(() => {
    localStorage.setItem('ji_extra_departments', JSON.stringify(extraDepartments))
  }, [extraDepartments])

  // Re-fetch students when extra departments change
  useEffect(() => {
    if (extraDepartments.length > 0) {
      fetchMultiDeptStudents()
    } else {
      // Reset department meta and filter when going back to single dept
      setDepartmentMeta([])
      setStudentDeptFilter([])
      fetchDashboardData()
    }
    // Invalidate exam data so it re-fetches with new departments
    setExamLoaded(false)
  }, [extraDepartments.length])

  // Fetch exam data when exam tab is selected for the first time
  useEffect(() => {
    if (activeTab === 'exam' && !examLoaded && !examLoading) {
      fetchExamData()
    }
  }, [activeTab])

  const fetchExamData = async (overrideAdminKey) => {
    setExamLoading(true)
    try {
      const key = overrideAdminKey || adminKey
      const params = new URLSearchParams()
      if (key) params.set('adminKey', key)
      if (extraDepartments.length > 0) params.set('departments', extraDepartments.join(','))
      const qs = params.toString()
      const url = qs ? `${API_BASE}/exam/students?${qs}` : `${API_BASE}/exam/students`
      console.log('[EXAM] Fetching with URL:', url, 'extraDepts:', extraDepartments)
      const res = await fetch(url, { credentials: 'include' })
      if (!res.ok) {
        if (res.status === 401) {
          onLogout()
          return
        }
        throw new Error('Failed to fetch exam data')
      }
      const data = await res.json()
      if (data.success) {
        setExamStudents(data.students)
        setExamSummary(data.examSummary)
        setExamLoaded(true)

        // Fetch scheduler status in admin mode
        if (key) {
          fetch(`${API_BASE}/exam/sync-scheduler/status`, { credentials: 'include' })
            .then(r => r.ok ? r.json() : null)
            .then(d => { if (d?.success) setSchedulerInfo(d.scheduler) })
            .catch(() => {})
        }
      }
    } catch (err) {
      setError('Failed to load exam data. Please try again.')
      console.error('[DASHBOARD] Exam data error:', err)
    } finally {
      setExamLoading(false)
    }
  }

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

  const fetchMultiDeptStudents = async () => {
    setLoading(true)
    setError(null)
    try {
      const deptIds = extraDepartments.join(',')
      const res = await fetch(
        `${API_BASE}/dashboard/students/multi?departments=${encodeURIComponent(deptIds)}`,
        { credentials: 'include' }
      )
      if (!res.ok) {
        if (res.status === 401) { onLogout(); return }
        throw new Error('Failed to fetch multi-department data')
      }
      const data = await res.json()
      if (data.success) {
        setStudents(data.students)
        setSummary(data.summary)
        setDepartmentMeta(data.departments || [])
        setLastSynced(new Date())

        // Warn about failed departments
        const failed = (data.departments || []).filter(d => d.status === 'error')
        if (failed.length > 0) {
          setDeptError(`Could not load ${failed.length} department(s): ${failed.map(d => d.error || d.id).join(', ')}`)
        }
      }
    } catch (err) {
      setError('Failed to load multi-department data. Please try again.')
      console.error('[DASHBOARD] Multi-dept error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleAddDepartment = () => {
    const id = deptInputValue.trim()
    const guidPattern = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/
    if (!guidPattern.test(id)) {
      setDeptError('Invalid Department ID format (must be a GUID like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)')
      return
    }
    if (id.toLowerCase() === department?.id?.toLowerCase()) {
      setDeptError('This is already your primary department')
      return
    }
    if (extraDepartments.some(d => d.toLowerCase() === id.toLowerCase())) {
      setDeptError('Department already added')
      return
    }
    if (extraDepartments.length >= 10) {
      setDeptError('Maximum 10 additional departments')
      return
    }
    setDeptError('')
    setDeptInputValue('')
    setExtraDepartments(prev => [...prev, id])
  }

  const handleRemoveDepartment = (id) => {
    setExtraDepartments(prev => prev.filter(d => d !== id))
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
      const body = extraDepartments.length > 0
        ? JSON.stringify({ extraDepartments })
        : undefined

      const response = await fetch(`${API_BASE}/dashboard/sync`, {
        method: 'POST',
        credentials: 'include',
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body,
      })

      if (!response.ok) {
        if (response.status === 401) {
          onLogout()
          return
        }
        const errData = await response.json().catch(() => null)
        throw new Error(errData?.error || `Sync failed (${response.status})`)
      }

      const data = await response.json()

      if (data.success) {
        setSummary(data.summary)
        setStudents(data.students)
        if (data.departments) setDepartmentMeta(data.departments)
        setLastSynced(new Date())
        // Also refresh exam data if it was loaded
        if (examLoaded) {
          setExamLoaded(false)
          if (activeTab === 'exam') {
            fetchExamData()
          }
        }
      }
    } catch (err) {
      console.error('[SYNC] Error:', err)
      setError(err.message || 'Failed to sync data. Please try again.')
    } finally {
      setSyncing(false)
    }
  }

  const handleExport = async () => {
    try {
      const exportUrl = extraDepartments.length > 0
        ? `${API_BASE}/dashboard/export?departments=${encodeURIComponent(extraDepartments.join(','))}`
        : `${API_BASE}/dashboard/export`
      const response = await fetch(exportUrl, {
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

  const handleAdminLogin = async (password) => {
    try {
      const res = await fetch(`${API_BASE}/exam/admin-verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ password })
      })
      const data = await res.json()
      if (data.success) {
        setAdminMode(true)
        setAdminKey(password)
        setShowAdminInput(false)
        setAdminError('')
        // Re-fetch exam data with admin key to get tracking data
        setExamLoaded(false)
        fetchExamData(password)
      } else {
        setAdminError('Invalid password')
      }
    } catch {
      setAdminError('Failed to verify')
    }
  }

  const handleAdminLogout = () => {
    setAdminMode(false)
    setAdminKey('')
    setShowAdminInput(false)
    setAdminError('')
    // Re-fetch without admin data
    setExamLoaded(false)
    fetchExamData('')
  }

  const recalcExamSummary = (students) => {
    const total = students.length
    const passed = students.filter(s => (s.passFail || '').toUpperCase() === 'PASS').length
    const failed = students.filter(s => (s.passFail || '').toUpperCase() === 'FAIL').length
    const now = Date.now()
    let upcoming = 0, atRisk = 0
    students.forEach(s => {
      const dt = parseExamDateRaw(s.examDateRaw)
      const hasResult = (s.passFail || '').trim() !== ''
      if (dt > now && !hasResult) {
        upcoming++
        if (s.matched !== false && (s.progress?.value || 0) < 80) atRisk++
      }
    })
    const completedExams = passed + failed
    const passRate = completedExams > 0 ? Math.round(passed / completedExams * 1000) / 10 : 0
    return prev => ({
      ...prev,
      total, passed, failed, upcoming, atRisk, passRate,
      noResult: total - passed - failed - upcoming
    })
  }

  const handleUpdateResult = async (email, result) => {
    try {
      const res = await fetch(`${API_BASE}/exam/update-result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, result, adminKey })
      })
      const data = await res.json()
      if (data.success) {
        // Update local state immediately
        const updated = examStudents.map(s =>
          s.email === email ? { ...s, passFail: result } : s
        )
        setExamStudents(updated)
        // Recalculate KPIs
        setExamSummary(recalcExamSummary(updated))
        // Also update selectedStudent if viewing this student
        setSelectedStudent(prev =>
          prev && prev.email === email ? { ...prev, passFail: result } : prev
        )
        if (!data.sheetSaved) {
          alert('Warning: Result saved locally but failed to save to Google Sheet. It may be lost after server restart. Check GOOGLE_SHEETS_CREDENTIALS_JSON env var.')
        }
      } else {
        alert('Failed to save result: ' + (data.error || 'Unknown error'))
      }
    } catch (err) {
      console.error('Failed to update result:', err)
      alert('Failed to save result. Check console for details.')
    }
  }

  const handleUpdateExamDate = async (email, newDate, newTime) => {
    try {
      const res = await fetch(`${API_BASE}/exam/update-date`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, date: newDate, time: newTime || '', adminKey })
      })
      const data = await res.json()
      if (data.success) {
        // Format date for display (e.g., "Jan 15, 2026")
        // Parse date as local time to avoid timezone shift
        const [year, month, day] = newDate.split('-').map(Number)
        const dt = new Date(year, month - 1, day)
        const formatted = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

        // Update local state immediately
        const updated = examStudents.map(s =>
          s.email === email ? {
            ...s,
            examDateRaw: newDate,
            examDate: formatted,
            examTime: newTime || s.examTime
          } : s
        )
        setExamStudents(updated)
        // Recalculate KPIs (upcoming, at-risk depend on exam date)
        setExamSummary(recalcExamSummary(updated))
        // Also update selectedStudent if viewing this student
        setSelectedStudent(prev =>
          prev && prev.email === email ? {
            ...prev,
            examDateRaw: newDate,
            examDate: formatted,
            examTime: newTime || prev.examTime
          } : prev
        )
        if (!data.sheetSaved) {
          alert('Warning: Date saved locally but failed to save to Google Sheet. It may be lost after server restart.')
        }
      } else {
        alert('Failed to save date: ' + (data.error || 'Unknown error'))
      }
    } catch (err) {
      console.error('Failed to update exam date:', err)
      alert('Failed to save date. Check console for details.')
    }
  }

  const handleUpdateStudentContact = async (studentId, contactData) => {
    try {
      const res = await fetch(`${API_BASE}/students/${studentId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(contactData)
      })
      const data = await res.json()
      if (data.success) {
        const updated = data.student
        // Update students list
        setStudents(prev => prev.map(s =>
          s.id === studentId ? {
            ...s,
            firstName: updated.firstName,
            lastName: updated.lastName,
            fullName: `${updated.firstName} ${updated.lastName}`.trim(),
            email: updated.emailAddress,
            phone: updated.phone
          } : s
        ))
        return { success: true, student: updated }
      } else {
        return { success: false, error: data.error || 'Update failed' }
      }
    } catch (err) {
      console.error('Failed to update student contact:', err)
      return { success: false, error: 'Network error' }
    }
  }

  const handleUpdateSheetContact = async (email, name, newEmail, phone) => {
    try {
      const res = await fetch(`${API_BASE}/exam/update-contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, name, newEmail, phone, adminKey })
      })
      const data = await res.json()
      if (data.success) {
        // Update local state
        const updated = examStudents.map(s =>
          s.email === email ? {
            ...s,
            fullName: name || s.fullName,
            email: newEmail || s.email,
            phone: phone || s.phone,
            sheetTracking: { ...s.sheetTracking, phone: phone || s.sheetTracking?.phone }
          } : s
        )
        setExamStudents(updated)
        // Update selected student
        setSelectedStudent(prev =>
          prev && prev.email === email ? {
            ...prev,
            fullName: name || prev.fullName,
            email: newEmail || prev.email,
            phone: phone || prev.phone,
            sheetTracking: { ...prev.sheetTracking, phone: phone || prev.sheetTracking?.phone }
          } : prev
        )
        if (!data.sheetSaved) {
          alert('Warning: Contact saved locally but failed to save to Google Sheet. Check GOOGLE_SHEETS_CREDENTIALS_JSON env var.')
        }
      } else {
        alert('Failed to save contact: ' + (data.error || 'Unknown error'))
      }
    } catch (err) {
      console.error('Failed to update sheet contact:', err)
      alert('Failed to save contact. Check console for details.')
    }
  }

  // Build unique department names for Students tab filter
  const studentDepartments = [...new Set(
    students.map(s => (s.departmentName || '').trim()).filter(Boolean)
  )].sort()

  // Filter students (works for both tabs)
  const filteredStudents = students.filter(student => {
    const searchLower = searchTerm.toLowerCase()
    const matchesSearch = !searchTerm ||
      student.fullName.toLowerCase().includes(searchLower) ||
      student.email.toLowerCase().includes(searchLower) ||
      (student.departmentName || '').toLowerCase().includes(searchLower)

    const matchesStatus = statusFilter === 'all' ||
      student.status.status.toLowerCase() === statusFilter.toLowerCase()

    const matchesDept = studentDeptFilter.length === 0 ||
      studentDeptFilter.includes((student.departmentName || '').trim())

    return matchesSearch && matchesStatus && matchesDept
  })

  // Helper: compute readiness for an exam student (GREEN/RED/GRAY)
  // Only based on pass/fail result - study readiness shown in student modal
  const getReadiness = (student) => {
    const pf = (student.passFail || '').toUpperCase()
    if (pf === 'PASS') return 'GREEN'
    if (pf === 'FAIL') return 'RED'
    // No exam result = neutral gray (avoids red dots looking like FAIL)
    return 'GRAY'
  }

  // Parse examDateRaw which can be M/D/YYYY (sheet) or YYYY-MM-DD (override)
  const parseExamDateRaw = (raw) => {
    if (!raw) return 0
    // YYYY-MM-DD format (from date overrides)
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      return new Date(raw + 'T00:00:00').getTime()
    }
    // M/D/YYYY format (from Google Sheet CSV)
    const parts = raw.split('/')
    if (parts.length === 3) {
      return new Date(parts[2], parts[0] - 1, parts[1]).getTime()
    }
    // Fallback
    const d = new Date(raw)
    return isNaN(d.getTime()) ? 0 : d.getTime()
  }

  // Helper: compute days until exam and check filter match
  const matchesDaysFilter = (student, filter) => {
    if (filter === 'all') return true
    const examDateTs = parseExamDateRaw(student.examDateRaw)
    if (!examDateTs) return filter === 'no-date'

    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayTs = today.getTime()
    const daysUntil = Math.ceil((examDateTs - todayTs) / 86400000)

    switch (filter) {
      case 'overdue': return daysUntil < 0
      case 'today': return daysUntil === 0
      case 'tomorrow': return daysUntil === 1
      case '2-days': return daysUntil >= 0 && daysUntil <= 2
      case '3-days': return daysUntil >= 0 && daysUntil <= 3
      case 'this-week': return daysUntil >= 0 && daysUntil <= 7
      case 'next-week': return daysUntil > 7 && daysUntil <= 14
      case 'this-month': return daysUntil >= 0 && daysUntil <= 30
      case 'no-date': return false
      default: return true
    }
  }

  const filteredExamStudents = examStudents.filter(student => {
    // In normal mode, only show students from logged-in department (matched in Absorb)
    if (!adminMode && student.matched === false) return false

    const searchLower = searchTerm.toLowerCase()
    const matchesSearch = !searchTerm ||
      (student.fullName || '').toLowerCase().includes(searchLower) ||
      (student.email || '').toLowerCase().includes(searchLower) ||
      (student.departmentName || '').toLowerCase().includes(searchLower) ||
      (student.agencyOwner || '').toLowerCase().includes(searchLower)

    // Exam result filter
    let matchesResult = true
    if (examResultFilter !== 'all') {
      const pf = (student.passFail || '').toUpperCase()
      const examDateTs = parseExamDateRaw(student.examDateRaw)
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const isPast = examDateTs && examDateTs < today.getTime()
      const hasResult = pf === 'PASS' || pf === 'FAIL'

      switch (examResultFilter) {
        case 'passed': matchesResult = pf === 'PASS'; break
        case 'failed': matchesResult = pf === 'FAIL'; break
        case 'no-result': matchesResult = !hasResult; break
        case 'upcoming': matchesResult = !isPast && !hasResult; break
        case 'pending': matchesResult = isPast && !hasResult; break
        case 'at-risk':
          matchesResult = !isPast && !hasResult && student.matched !== false && (student.progress?.value || 0) < 80
          break
        default: matchesResult = true
      }
    }

    // Course type filter
    const matchesCourse = examCourseFilter === 'all' ||
      (student.examCourse || '').toLowerCase() === examCourseFilter.toLowerCase()

    // Department filter
    const matchesDept = examDeptFilter.length === 0 ||
      examDeptFilter.includes((student.departmentName || '').trim())

    // State filter
    const matchesState = examStateFilter === 'all' ||
      (student.examState || '').toLowerCase() === examStateFilter.toLowerCase()

    // Readiness filter (uses backend study readiness, not pass/fail dot color)
    const matchesReadiness = examReadinessFilter === 'all' ||
      (student.readiness?.status || 'GRAY') === examReadinessFilter

    // Days until exam filter
    const matchesDays = matchesDaysFilter(student, examDaysFilter)

    return matchesSearch && matchesResult && matchesCourse && matchesDept && matchesState && matchesReadiness && matchesDays
  })

  // Get unique values for filter dropdowns
  const visibleExamStudents = adminMode ? examStudents : examStudents.filter(s => s.matched !== false)
  const examCourseTypes = [...new Set(visibleExamStudents.map(s => (s.examCourse || '').trim()).filter(Boolean))].sort()
  const examDepartments = [...new Set(visibleExamStudents.map(s => (s.departmentName || '').trim()).filter(Boolean))].sort()
  const examStates = [...new Set(visibleExamStudents.map(s => (s.examState || '').trim()).filter(Boolean))].sort()

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
          <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
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
        <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
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
      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

        {/* Tab Navigation */}
        <div className="flex space-x-1 mb-6 bg-white rounded-lg shadow-md p-1 max-w-xs">
          <button
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'students'
                ? 'bg-ji-blue-bright text-white shadow-sm'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
            onClick={() => setActiveTab('students')}
          >
            <div className="flex items-center justify-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Students</span>
            </div>
          </button>
          <button
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'exam'
                ? 'bg-ji-blue-bright text-white shadow-sm'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
            onClick={() => setActiveTab('exam')}
          >
            <div className="flex items-center justify-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>Exam</span>
            </div>
          </button>
        </div>

        {/* Students Tab Content */}
        {activeTab === 'students' && (
          <>
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

            {/* Department Manager */}
            <div className="bg-white rounded-xl shadow-md p-4 mb-6">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <svg className="w-5 h-5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                  <span className="text-sm font-medium text-gray-700">
                    Departments ({1 + extraDepartments.length})
                  </span>
                  <span className="px-2 py-0.5 bg-ji-blue-bright/10 text-ji-blue-bright text-xs rounded-full font-medium">
                    {department?.name || 'Primary'}
                  </span>
                  {departmentMeta
                    .filter(d => d.status === 'ok' && d.id !== department?.id)
                    .map(d => (
                      <span key={d.id} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full flex items-center gap-1">
                        {d.name} ({d.studentCount})
                        <button
                          onClick={() => handleRemoveDepartment(d.id)}
                          className="text-red-400 hover:text-red-600 ml-0.5"
                          title="Remove department"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </span>
                    ))
                  }
                  {/* Show IDs that haven't resolved to names yet */}
                  {extraDepartments
                    .filter(id => !departmentMeta.some(d => d.id === id && d.status === 'ok'))
                    .map(id => (
                      <span key={id} className="px-2 py-0.5 bg-yellow-50 text-yellow-700 text-xs rounded-full flex items-center gap-1">
                        {id.substring(0, 8)}...
                        <button
                          onClick={() => handleRemoveDepartment(id)}
                          className="text-red-400 hover:text-red-600 ml-0.5"
                          title="Remove department"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </span>
                    ))
                  }
                </div>
                <button
                  onClick={() => { setShowDeptManager(!showDeptManager); setDeptError('') }}
                  className="text-sm text-ji-blue-bright hover:text-ji-blue-medium flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={showDeptManager ? "M5 15l7-7 7 7" : "M12 4v16m8-8H4"} />
                  </svg>
                  <span>{showDeptManager ? 'Close' : 'Add Department'}</span>
                </button>
              </div>

              {showDeptManager && (
                <div className="mt-3 flex gap-2 items-start">
                  <div className="flex-1">
                    <input
                      type="text"
                      placeholder="Paste Department ID (e.g. a1b2c3d4-e5f6-7890-abcd-ef1234567890)"
                      value={deptInputValue}
                      onChange={(e) => { setDeptInputValue(e.target.value); setDeptError('') }}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddDepartment()}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ji-blue-bright"
                    />
                    {deptError && <p className="text-red-500 text-xs mt-1">{deptError}</p>}
                  </div>
                  <button
                    onClick={handleAddDepartment}
                    className="btn btn-primary text-sm py-2 px-4 whitespace-nowrap"
                  >
                    Add
                  </button>
                </div>
              )}
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
                    placeholder="Search by name, email, or department..."
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                <div className="flex items-center gap-4 flex-wrap">
                  {/* Department Filter - multi-select checklist */}
                  {extraDepartments.length > 0 && studentDepartments.length > 1 && (
                    <div className="relative">
                      <button
                        onClick={() => setShowDeptDropdown(!showDeptDropdown)}
                        className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright bg-white flex items-center gap-2 text-sm"
                      >
                        <span>
                          {studentDeptFilter.length === 0
                            ? 'All Departments'
                            : `${studentDeptFilter.length} dept${studentDeptFilter.length > 1 ? 's' : ''}`}
                        </span>
                        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={showDeptDropdown ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"} />
                        </svg>
                      </button>
                      {showDeptDropdown && (
                        <>
                          <div className="fixed inset-0 z-10" onClick={() => setShowDeptDropdown(false)} />
                          <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[200px] py-1">
                            <label className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm border-b border-gray-100">
                              <input
                                type="checkbox"
                                checked={studentDeptFilter.length === 0}
                                onChange={() => setStudentDeptFilter([])}
                                className="rounded text-ji-blue-bright"
                              />
                              <span className="font-medium">All Departments</span>
                            </label>
                            {studentDepartments.map(d => (
                              <label key={d} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm">
                                <input
                                  type="checkbox"
                                  checked={studentDeptFilter.includes(d)}
                                  onChange={() => {
                                    setStudentDeptFilter(prev =>
                                      prev.includes(d)
                                        ? prev.filter(x => x !== d)
                                        : [...prev, d]
                                    )
                                  }}
                                  className="rounded text-ji-blue-bright"
                                />
                                <span className="truncate">{d}</span>
                              </label>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  )}

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
                    <option value="abandoned">Abandoned</option>
                    <option value="course expired">Course Expired</option>
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
                {extraDepartments.length > 0 && ` across ${1 + extraDepartments.length} departments`}
              </div>
            </div>

            {/* Student Table */}
            <StudentTable
              students={filteredStudents}
              onViewStudent={setSelectedStudent}
              showDepartment={extraDepartments.length > 0}
            />
          </>
        )}

        {/* Exam Tab Content */}
        {activeTab === 'exam' && (
          <>
            {/* Exam Tab Header */}
            <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-4">
                <p className="text-sm text-gray-500">
                  Exam scheduling, pass rates & study tracking
                </p>
                <button
                  onClick={() => fetchExamData()}
                  disabled={examLoading}
                  className="text-sm text-ji-blue-bright hover:text-ji-blue-medium flex items-center space-x-1"
                >
                  <svg className={`w-4 h-4 ${examLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span>{examLoading ? 'Refreshing...' : 'Refresh'}</span>
                </button>
              </div>
              <div className="flex items-center gap-3">
                {/* Admin Mode Toggle */}
                {adminMode ? (
                  <div className="flex items-center gap-2">
                    {/* Scheduler status indicator */}
                    {schedulerInfo && (
                      <span className={`text-xs px-2 py-1 rounded-lg border ${
                        schedulerInfo.enabled
                          ? 'text-green-600 border-green-200 bg-green-50'
                          : 'text-gray-500 border-gray-200 bg-gray-50'
                      }`} title={schedulerInfo.lastSync ? `Last: ${new Date(schedulerInfo.lastSync).toLocaleString()}` : 'No sync yet'}>
                        {schedulerInfo.enabled
                          ? `Auto-sync: every ${schedulerInfo.intervalHours}h${schedulerInfo.lastSync ? ` | Last: ${(() => {
                              const mins = Math.round((Date.now() - new Date(schedulerInfo.lastSync).getTime()) / 60000)
                              if (mins < 1) return 'just now'
                              if (mins < 60) return `${mins}m ago`
                              const hrs = Math.round(mins / 60)
                              return `${hrs}h ago`
                            })()}` : ''}`
                          : 'Auto-sync: not configured'
                        }
                      </span>
                    )}

                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                      </svg>
                      Admin Mode
                    </span>
                    <button
                      onClick={handleAdminLogout}
                      className="text-xs text-gray-500 hover:text-red-500"
                    >
                      Exit
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <button
                      onClick={() => setShowAdminInput(!showAdminInput)}
                      className="text-sm text-purple-500 hover:text-purple-700 flex items-center space-x-1 px-2.5 py-1 rounded-lg border border-purple-200 hover:border-purple-400 hover:bg-purple-50 transition-colors"
                      title="Admin Override"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      <span>Admin</span>
                    </button>
                    {showAdminInput && (
                      <div className="absolute right-0 top-8 bg-white rounded-lg shadow-lg border p-3 z-50 w-64">
                        <p className="text-xs text-gray-500 mb-2">Enter admin password to view all student data</p>
                        <form onSubmit={(e) => { e.preventDefault(); handleAdminLogin(e.target.password.value) }}>
                          <input
                            name="password"
                            type="password"
                            placeholder="Admin password"
                            className="w-full px-3 py-1.5 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                            autoFocus
                          />
                          {adminError && <p className="text-xs text-red-500 mt-1">{adminError}</p>}
                          <div className="flex gap-2 mt-2">
                            <button type="submit" className="flex-1 px-3 py-1.5 bg-purple-600 text-white rounded text-xs font-medium hover:bg-purple-700">
                              Unlock
                            </button>
                            <button type="button" onClick={() => { setShowAdminInput(false); setAdminError('') }} className="px-3 py-1.5 bg-gray-100 rounded text-xs text-gray-600 hover:bg-gray-200">
                              Cancel
                            </button>
                          </div>
                        </form>
                      </div>
                    )}
                  </div>
                )}
                <button
                  onClick={() => setShowExamCharts(!showExamCharts)}
                  className="text-sm text-ji-blue-bright hover:text-ji-blue-medium flex items-center space-x-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>{showExamCharts ? 'Hide Charts' : 'Show Charts'}</span>
                </button>
              </div>
            </div>

            {/* Exam Charts (collapsible) */}
            {showExamCharts && examSummary && (
              <div className="mb-8 animate-fadeIn">
                <ExamCharts examSummary={examSummary} students={examStudents} />
              </div>
            )}

            {/* Exam KPI Row 1 - Core Metrics */}
            {examSummary && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-4">
                  <div className="kpi-card bg-gray-50 border-l-4 border-gray-500 animate-fadeIn">
                    <p className="text-sm font-medium text-gray-600">Total Students</p>
                    <p className="kpi-value text-gray-800">{examSummary.total}</p>
                    <p className="text-xs text-gray-500 mt-1">Exam scheduled</p>
                  </div>
                  <div className="kpi-card bg-blue-50 border-l-4 border-blue-500 animate-fadeIn" style={{animationDelay:'50ms'}}>
                    <p className="text-sm font-medium text-gray-600">Upcoming</p>
                    <p className="kpi-value text-blue-800">{examSummary.upcoming}</p>
                    <p className="text-xs text-gray-500 mt-1">Exams scheduled</p>
                  </div>
                  <div className="kpi-card bg-green-50 border-l-4 border-green-500 animate-fadeIn" style={{animationDelay:'100ms'}}>
                    <p className="text-sm font-medium text-gray-600">Pass Rate</p>
                    <p className="kpi-value text-green-800">{examSummary.passRate}%</p>
                    <p className="text-xs text-gray-500 mt-1">{examSummary.passed} passed / {examSummary.passed + examSummary.failed} taken</p>
                  </div>
                  <div className="kpi-card bg-red-50 border-l-4 border-red-500 animate-fadeIn" style={{animationDelay:'150ms'}}>
                    <p className="text-sm font-medium text-gray-600">Failed</p>
                    <p className="kpi-value text-red-800">{examSummary.failed}</p>
                    <p className="text-xs text-gray-500 mt-1">Exam result</p>
                  </div>
                  <div className="kpi-card bg-amber-50 border-l-4 border-amber-500 animate-fadeIn" style={{animationDelay:'200ms'}}>
                    <p className="text-sm font-medium text-gray-600">At Risk</p>
                    <p className="kpi-value text-amber-800">{examSummary.atRisk}</p>
                    <p className="text-xs text-gray-500 mt-1">Upcoming + &lt;80% progress</p>
                  </div>
                </div>

                {/* KPI Row 2 - Study Time Analytics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div className="kpi-card bg-purple-50 border-l-4 border-purple-500 animate-fadeIn" style={{animationDelay:'250ms'}}>
                    <p className="text-sm font-medium text-gray-600">Avg Study Time</p>
                    <p className="kpi-value text-purple-800">{examSummary.avgStudyTimeFormatted}</p>
                    <p className="text-xs text-gray-500 mt-1">All tracked students</p>
                  </div>
                  <div className="kpi-card bg-green-50 border-l-4 border-green-400 animate-fadeIn" style={{animationDelay:'300ms'}}>
                    <p className="text-sm font-medium text-gray-600">Avg Time (Passed)</p>
                    <p className="kpi-value text-green-700">{examSummary.avgStudyPassedFormatted}</p>
                    <p className="text-xs text-gray-500 mt-1">Students who passed</p>
                  </div>
                  <div className="kpi-card bg-red-50 border-l-4 border-red-400 animate-fadeIn" style={{animationDelay:'350ms'}}>
                    <p className="text-sm font-medium text-gray-600">Avg Time (Failed)</p>
                    <p className="kpi-value text-red-700">{examSummary.avgStudyFailedFormatted}</p>
                    <p className="text-xs text-gray-500 mt-1">Students who failed</p>
                  </div>
                  <div className="kpi-card bg-indigo-50 border-l-4 border-indigo-500 animate-fadeIn" style={{animationDelay:'400ms'}}>
                    <p className="text-sm font-medium text-gray-600">Avg Progress</p>
                    <p className="kpi-value text-indigo-800">{examSummary.averageProgress}%</p>
                    <p className="text-xs text-gray-500 mt-1">Course completion</p>
                  </div>
                </div>

                {/* Course Type Pass Rates */}
                {examSummary.courseTypes && Object.keys(examSummary.courseTypes).length > 0 && (
                  <div className="bg-white rounded-xl shadow-md p-4 mb-6">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Pass Rate by Course Type</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {Object.entries(examSummary.courseTypes).map(([course, data]) => {
                        const taken = data.passed + data.failed
                        const rate = taken > 0 ? Math.round(data.passed / taken * 100) : null
                        return (
                          <div key={course} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div>
                              <p className="font-medium text-gray-900 text-sm">{course}</p>
                              <p className="text-xs text-gray-500">{data.total} students</p>
                            </div>
                            <div className="text-right">
                              {rate !== null ? (
                                <>
                                  <p className={`text-lg font-bold ${rate >= 70 ? 'text-green-600' : rate >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                                    {rate}%
                                  </p>
                                  <p className="text-xs text-gray-500">{data.passed}P / {data.failed}F</p>
                                </>
                              ) : (
                                <p className="text-sm text-gray-400">No results</p>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Search/Filter for Exam Tab */}
            <div className="bg-white rounded-xl shadow-md p-4 mb-6">
              {/* Row 1: Search + Result filter */}
              <div className="flex flex-col sm:flex-row gap-3 items-center">
                <div className="relative flex-1 max-w-md">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </span>
                  <input
                    type="text"
                    placeholder="Search by name or email..."
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright text-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                {/* Exam Result Filter */}
                <select
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright text-sm"
                  value={examResultFilter}
                  onChange={(e) => setExamResultFilter(e.target.value)}
                >
                  <option value="no-result">No Result</option>
                  <option value="all">All Results</option>
                  <option value="upcoming">Upcoming</option>
                  <option value="passed">Passed</option>
                  <option value="failed">Failed</option>
                  <option value="pending">Pending</option>
                  <option value="at-risk">At Risk</option>
                </select>
              </div>

              {/* Row 2: All other filters */}
              <div className="flex items-center gap-3 flex-wrap mt-3">
                {/* Department Filter - multi-select checklist */}
                <div className="relative">
                  <button
                    onClick={() => setShowExamDeptDropdown(!showExamDeptDropdown)}
                    className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright bg-white flex items-center gap-2 text-sm"
                  >
                    <span>
                      {examDeptFilter.length === 0
                        ? 'All Departments'
                        : `${examDeptFilter.length} dept${examDeptFilter.length > 1 ? 's' : ''}`}
                    </span>
                    <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={showExamDeptDropdown ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"} />
                    </svg>
                  </button>
                  {showExamDeptDropdown && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setShowExamDeptDropdown(false)} />
                      <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[200px] py-1">
                        <label className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm border-b border-gray-100">
                          <input
                            type="checkbox"
                            checked={examDeptFilter.length === 0}
                            onChange={() => setExamDeptFilter([])}
                            className="rounded text-ji-blue-bright"
                          />
                          <span className="font-medium">All Departments</span>
                        </label>
                        {examDepartments.map(d => (
                          <label key={d} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm">
                            <input
                              type="checkbox"
                              checked={examDeptFilter.includes(d)}
                              onChange={() => {
                                setExamDeptFilter(prev =>
                                  prev.includes(d)
                                    ? prev.filter(x => x !== d)
                                    : [...prev, d]
                                )
                              }}
                              className="rounded text-ji-blue-bright"
                            />
                            <span className="truncate">{d}</span>
                          </label>
                        ))}
                      </div>
                    </>
                  )}
                </div>

                {/* Readiness Filter */}
                <select
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright text-sm"
                  value={examReadinessFilter}
                  onChange={(e) => setExamReadinessFilter(e.target.value)}
                >
                  <option value="all">All Readiness</option>
                  <option value="GREEN">Green - On Track</option>
                  <option value="YELLOW">Yellow - Needs Attention</option>
                  <option value="RED">Red - At Risk</option>
                </select>

                {/* Days Until Exam Filter */}
                <select
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright text-sm"
                  value={examDaysFilter}
                  onChange={(e) => setExamDaysFilter(e.target.value)}
                >
                  <option value="all">All Dates</option>
                  <option value="overdue">Overdue</option>
                  <option value="today">Today</option>
                  <option value="tomorrow">Tomorrow</option>
                  <option value="2-days">Within 2 Days</option>
                  <option value="3-days">Within 3 Days</option>
                  <option value="this-week">This Week</option>
                  <option value="next-week">Next 2 Weeks</option>
                  <option value="this-month">This Month</option>
                </select>

                {/* State Filter */}
                <select
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright text-sm"
                  value={examStateFilter}
                  onChange={(e) => setExamStateFilter(e.target.value)}
                >
                  <option value="all">All States</option>
                  {examStates.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>

                {/* Course Type Filter */}
                <select
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-ji-blue-bright text-sm"
                  value={examCourseFilter}
                  onChange={(e) => setExamCourseFilter(e.target.value)}
                >
                  <option value="all">All Courses</option>
                  {examCourseTypes.map(ct => (
                    <option key={ct} value={ct}>{ct}</option>
                  ))}
                </select>

                {/* Clear Filters Button */}
                {(examDeptFilter.length > 0 || examReadinessFilter !== 'all' || examDaysFilter !== 'all' || examStateFilter !== 'all' || examCourseFilter !== 'all' || examResultFilter !== 'all' || searchTerm) && (
                  <button
                    onClick={() => {
                      setExamDeptFilter([])
                      setExamReadinessFilter('all')
                      setExamDaysFilter('all')
                      setExamStateFilter('all')
                      setExamCourseFilter('all')
                      setExamResultFilter('all')
                      setSearchTerm('')
                    }}
                    className="px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors border border-red-200"
                  >
                    Clear All
                  </button>
                )}
              </div>

              <div className="mt-3 text-sm text-gray-500">
                Showing {filteredExamStudents.length} of {visibleExamStudents.length} exam students
              </div>
            </div>

            {/* Exam Loading State */}
            {examLoading && !examLoaded ? (
              <div className="bg-white rounded-xl shadow-md p-8 text-center">
                <div className="spinner mx-auto mb-4"></div>
                <p className="text-gray-500">Loading exam schedule...</p>
              </div>
            ) : (
              <ExamTable
                students={filteredExamStudents}
                onViewStudent={setSelectedStudent}
                adminMode={adminMode}
              />
            )}
          </>
        )}
      </main>

      {/* Student Detail Modal - Absorb data available */}
      {selectedStudent && selectedStudent.id && (
        <StudentModal
          studentId={selectedStudent.id}
          examInfo={selectedStudent.examDate ? {
            examDate: selectedStudent.examDate,
            examDateRaw: selectedStudent.examDateRaw,
            examTime: selectedStudent.examTime,
            examState: selectedStudent.examState,
            examCourse: selectedStudent.examCourse,
            agencyOwner: selectedStudent.agencyOwner,
            passFail: selectedStudent.passFail,
            finalOutcome: selectedStudent.finalOutcome,
            departmentName: selectedStudent.departmentName,
            sheetTracking: selectedStudent.sheetTracking,
            email: selectedStudent.email
          } : null}
          onClose={() => setSelectedStudent(null)}
          onSessionExpired={onLogout}
          onUpdateResult={activeTab === 'exam' ? handleUpdateResult : null}
          onUpdateExamDate={activeTab === 'exam' ? handleUpdateExamDate : null}
          onUpdateStudentContact={handleUpdateStudentContact}
        />
      )}

      {/* Exam Sheet Modal - No Absorb data, show sheet info */}
      {selectedStudent && !selectedStudent.id && (
        <ExamSheetModal
          student={selectedStudent}
          adminMode={adminMode}
          onClose={() => setSelectedStudent(null)}
          onUpdateResult={handleUpdateResult}
          onUpdateExamDate={handleUpdateExamDate}
          onUpdateContact={handleUpdateSheetContact}
        />
      )}
    </div>
  )
}

export default Dashboard
