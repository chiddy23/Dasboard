import React, { useState, useEffect, useMemo } from 'react'
import StatusBadge from './StatusBadge'
import ProgressBar from './ProgressBar'

const API_BASE = '/api'

// Format decimal hours to readable string like "4h 48m", "42m", "9h 54m"
function formatHours(decimalHours) {
  if (!decimalHours || decimalHours <= 0) return '0m'
  const totalMinutes = Math.round(decimalHours * 60)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

// Helper to check if course is pre-licensing related
function isPreLicensingCourse(name) {
  const lower = name.toLowerCase()
  return lower.includes('pre-licens') || lower.includes('prelicens') || lower.includes('pre licens')
}

// Helper to check if course is a chapter/module
function isChapterOrModule(name) {
  const lower = name.toLowerCase()
  return lower.includes('module') || lower.includes('chapter') || lower.includes('lesson') || lower.includes('unit')
}

// Helper to check if course is exam prep
function isExamPrepCourse(name) {
  const lower = name.toLowerCase()
  return lower.includes('practice') || lower.includes('prep') || lower.includes('study')
}

// Helper to categorize courses
function categorizeEnrollments(enrollments) {
  const preLicensing = []
  const examPrep = []
  const other = []

  for (const enrollment of enrollments) {
    const name = enrollment.courseName || ''

    if (isPreLicensingCourse(name)) {
      // Pre-licensing course (main or chapter)
      preLicensing.push(enrollment)
    } else if (isChapterOrModule(name)) {
      // Chapters/modules without "pre-license" - likely part of curriculum
      preLicensing.push(enrollment)
    } else if (isExamPrepCourse(name)) {
      // Exam prep / practice courses
      examPrep.push(enrollment)
    } else {
      other.push(enrollment)
    }
  }

  return { preLicensing, examPrep, other }
}

// Calculate overall progress for a group
function calculateGroupProgress(enrollments) {
  if (!enrollments.length) return 0
  // progress is an object with 'value' property from the backend
  const validEnrollments = enrollments.filter(e => {
    const progressVal = e.progress?.value ?? e.progress
    return typeof progressVal === 'number' && !isNaN(progressVal)
  })
  if (!validEnrollments.length) return 0
  const total = validEnrollments.reduce((sum, e) => {
    const progressVal = e.progress?.value ?? e.progress
    return sum + progressVal
  }, 0)
  return Math.round(total / validEnrollments.length)
}

// Enrollment Card Component
function EnrollmentCard({ enrollment, isModule = false }) {
  return (
    <div className={`border border-gray-200 rounded-lg p-4 ${isModule ? 'ml-4 bg-gray-50' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <p className={`font-medium text-gray-900 ${isModule ? 'text-sm' : ''}`}>
          {isModule && <span className="text-gray-400 mr-2">|--</span>}
          {enrollment.courseName}
        </p>
        <span className={`text-xs px-2 py-1 rounded-full ${
          enrollment.status === 2
            ? 'bg-green-100 text-green-800'
            : enrollment.status === 1
            ? 'bg-blue-100 text-blue-800'
            : 'bg-gray-100 text-gray-800'
        }`}>
          {enrollment.statusText}
        </span>
      </div>
      <ProgressBar progress={enrollment.progress} />
      <div className="flex items-center justify-between mt-2 text-sm text-gray-500">
        <span>Time: {enrollment.timeSpent?.formatted || '0m'}</span>
        <span>Last accessed: {enrollment.lastAccessed?.relative || 'Never'}</span>
      </div>
    </div>
  )
}

// Course Group Component
function CourseGroup({ title, icon, color, enrollments, defaultExpanded = true }) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const groupProgress = calculateGroupProgress(enrollments)

  if (!enrollments.length) return null

  // Find the main course (usually the one without specific module indicators)
  const mainCourse = enrollments.find(e => {
    const name = (e.courseName || '').toLowerCase()
    return !name.includes('module') && !name.includes('chapter') && !name.includes('lesson')
  }) || enrollments[0]

  const modules = enrollments.filter(e => e.id !== mainCourse.id)

  return (
    <div className={`border-2 rounded-xl overflow-hidden ${color}`}>
      {/* Group Header */}
      <div
        className="px-4 py-3 cursor-pointer flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <h4 className="font-bold text-gray-900">{title}</h4>
            <p className="text-sm text-gray-600">{enrollments.length} course{enrollments.length > 1 ? 's' : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900">{groupProgress}%</p>
            <p className="text-xs text-gray-500">Overall Progress</p>
          </div>
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Group Content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Main Course */}
          <EnrollmentCard enrollment={mainCourse} />

          {/* Modules */}
          {modules.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide ml-4">
                Modules ({modules.length})
              </p>
              {modules.map((module) => (
                <EnrollmentCard key={module.id} enrollment={module} isModule />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Main Enrollment Groups Component
function EnrollmentGroups({ enrollments }) {
  const { preLicensing, examPrep, other } = useMemo(
    () => categorizeEnrollments(enrollments),
    [enrollments]
  )

  return (
    <div className="space-y-4">
      {/* Pre-Licensing Bundle */}
      <CourseGroup
        title="Pre-Licensing Course"
        icon="📚"
        color="border-blue-200 bg-blue-50/50"
        enrollments={preLicensing}
        defaultExpanded={true}
      />

      {/* Exam Prep Bundle */}
      <CourseGroup
        title="Exam Prep"
        icon="📝"
        color="border-purple-200 bg-purple-50/50"
        enrollments={examPrep}
        defaultExpanded={true}
      />

      {/* Other Courses */}
      {other.length > 0 && (
        <CourseGroup
          title="Other Courses"
          icon="📖"
          color="border-gray-200 bg-gray-50/50"
          enrollments={other}
          defaultExpanded={false}
        />
      )}
    </div>
  )
}

function isValidEmail(email) {
  return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email)
}

function StudentModal({ studentId, examInfo, onClose, onSessionExpired, onUpdateResult, onUpdateExamDate, onUpdateStudentContact }) {
  const [student, setStudent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingDate, setEditingDate] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [newTime, setNewTime] = useState('')
  const [editingContact, setEditingContact] = useState(false)
  const [contactForm, setContactForm] = useState({ firstName: '', lastName: '', emailAddress: '', phone: '' })
  const [contactError, setContactError] = useState('')
  const [contactSaving, setContactSaving] = useState(false)
  const [snapshots, setSnapshots] = useState([])
  const [snapshotsExpanded, setSnapshotsExpanded] = useState(false)

  useEffect(() => {
    fetchStudentDetails()
  }, [studentId])

  const fetchStudentDetails = async () => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (examInfo?.examCourse) params.set('courseType', examInfo.examCourse)
      const qs = params.toString() ? `?${params.toString()}` : ''
      const response = await fetch(`${API_BASE}/students/${studentId}${qs}`, {
        credentials: 'include'
      })

      if (!response.ok) {
        if (response.status === 401) {
          onSessionExpired()
          return
        }
        throw new Error('Failed to fetch student details')
      }

      const data = await response.json()

      if (data.success) {
        setStudent(data.student)
        // Fetch study snapshots in background
        if (data.student?.email) {
          fetch(`${API_BASE}/exam/snapshots/${encodeURIComponent(data.student.email)}`, { credentials: 'include' })
            .then(r => r.ok ? r.json() : null)
            .then(d => { if (d?.success) setSnapshots(d.snapshots || []) })
            .catch(() => {})
        }
      } else {
        throw new Error(data.error || 'Failed to load student')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveContact = async () => {
    setContactError('')
    if (!contactForm.firstName.trim() || !contactForm.lastName.trim()) {
      setContactError('First and last name are required')
      return
    }
    if (!isValidEmail(contactForm.emailAddress)) {
      setContactError('Please enter a valid email address')
      return
    }
    setContactSaving(true)
    try {
      const result = await onUpdateStudentContact(studentId, {
        firstName: contactForm.firstName.trim(),
        lastName: contactForm.lastName.trim(),
        emailAddress: contactForm.emailAddress.trim(),
        phone: contactForm.phone.trim()
      })
      if (result.success) {
        setStudent(prev => ({
          ...prev,
          firstName: result.student.firstName,
          lastName: result.student.lastName,
          fullName: `${result.student.firstName} ${result.student.lastName}`.trim(),
          email: result.student.emailAddress,
          phone: result.student.phone
        }))
        setEditingContact(false)
      } else {
        setContactError(result.error || 'Update failed')
      }
    } catch (err) {
      setContactError('Failed to save changes')
    } finally {
      setContactSaving(false)
    }
  }

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="header px-6 py-4 rounded-t-xl">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white">Student Details</h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading ? (
            <div className="text-center py-12">
              <div className="spinner mx-auto mb-4"></div>
              <p className="text-gray-500">Loading student details...</p>
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <svg className="w-12 h-12 mx-auto text-red-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-red-600">{error}</p>
              <button
                onClick={fetchStudentDetails}
                className="mt-4 btn btn-secondary"
              >
                Try Again
              </button>
            </div>
          ) : student ? (
            <div className="space-y-6">
              {/* Student Info */}
              <div className="flex items-start justify-between">
                {editingContact ? (
                  <div className="flex-1 mr-4">
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">First Name</label>
                        <input
                          type="text"
                          value={contactForm.firstName}
                          onChange={(e) => setContactForm(prev => ({ ...prev, firstName: e.target.value }))}
                          className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">Last Name</label>
                        <input
                          type="text"
                          value={contactForm.lastName}
                          onChange={(e) => setContactForm(prev => ({ ...prev, lastName: e.target.value }))}
                          className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                    <div className="mb-3">
                      <label className="text-xs text-gray-500 mb-1 block">Email</label>
                      <input
                        type="email"
                        value={contactForm.emailAddress}
                        onChange={(e) => setContactForm(prev => ({ ...prev, emailAddress: e.target.value }))}
                        className={`w-full px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 ${
                          contactForm.emailAddress && !isValidEmail(contactForm.emailAddress)
                            ? 'border-red-300 focus:ring-red-400'
                            : 'border-gray-300 focus:ring-blue-500'
                        }`}
                      />
                      {contactForm.emailAddress && !isValidEmail(contactForm.emailAddress) && (
                        <p className="text-xs text-red-500 mt-1">Invalid email format</p>
                      )}
                    </div>
                    <div className="mb-3">
                      <label className="text-xs text-gray-500 mb-1 block">Phone</label>
                      <input
                        type="tel"
                        value={contactForm.phone}
                        onChange={(e) => setContactForm(prev => ({ ...prev, phone: e.target.value }))}
                        className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="Optional"
                      />
                    </div>
                    {contactError && (
                      <p className="text-xs text-red-500 mb-2">{contactError}</p>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={handleSaveContact}
                        disabled={contactSaving || (contactForm.emailAddress && !isValidEmail(contactForm.emailAddress))}
                        className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
                      >
                        {contactSaving ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        onClick={() => { setEditingContact(false); setContactError('') }}
                        className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg text-xs hover:bg-gray-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900">{student.fullName}</h3>
                    <p className="text-gray-500">{student.email}</p>
                    {student.phone && <p className="text-gray-400 text-sm">{student.phone}</p>}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  {!editingContact && onUpdateStudentContact && (
                    <button
                      onClick={() => {
                        setEditingContact(true)
                        setContactForm({
                          firstName: student.firstName || '',
                          lastName: student.lastName || '',
                          emailAddress: student.email || '',
                          phone: student.phone || ''
                        })
                        setContactError('')
                      }}
                      className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors flex items-center gap-1 shadow-sm"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Edit
                    </button>
                  )}
                  <StatusBadge status={student.status} />
                </div>
              </div>

              {/* Exam Info (when viewing from Exam tab) */}
              {examInfo && (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                  <h4 className="font-bold text-gray-900 mb-3 flex items-center gap-2 text-sm">
                    <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    Exam Scheduling
                    {onUpdateExamDate && !editingDate && (
                      <button
                        onClick={() => {
                          setEditingDate(true)
                          setNewDate(examInfo.examDateRaw || '')
                          setNewTime(examInfo.examTime || '')
                        }}
                        className="ml-auto text-xs px-3 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors flex items-center gap-1 shadow-sm"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Edit Date
                      </button>
                    )}
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {editingDate && onUpdateExamDate ? (
                      <>
                        <div className="bg-white rounded-lg p-2.5">
                          <p className="text-xs text-gray-500 mb-1">Exam Date</p>
                          <input
                            type="date"
                            value={newDate}
                            onChange={(e) => setNewDate(e.target.value)}
                            className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div className="bg-white rounded-lg p-2.5">
                          <p className="text-xs text-gray-500 mb-1">Time</p>
                          <input
                            type="text"
                            value={newTime}
                            onChange={(e) => setNewTime(e.target.value)}
                            placeholder="e.g., 2:00 PM"
                            className="w-full px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div className="col-span-2 flex gap-2">
                          <button
                            onClick={() => {
                              if (newDate && examInfo.email) {
                                onUpdateExamDate(examInfo.email, newDate, newTime)
                                setEditingDate(false)
                              }
                            }}
                            className="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 transition-colors"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => setEditingDate(false)}
                            className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-xs hover:bg-gray-300 transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="bg-white rounded-lg p-2.5">
                          <p className="text-xs text-gray-500">Exam Date</p>
                          <p className="font-semibold text-gray-900 text-sm">{examInfo.examDate || 'TBD'}</p>
                        </div>
                        <div className="bg-white rounded-lg p-2.5">
                          <p className="text-xs text-gray-500">Time</p>
                          <p className="font-semibold text-gray-900 text-sm">{examInfo.examTime || 'N/A'}</p>
                        </div>
                      </>
                    )}
                    <div className="bg-white rounded-lg p-2.5">
                      <p className="text-xs text-gray-500">State</p>
                      <p className="font-semibold text-gray-900 text-sm">{examInfo.examState || 'N/A'}</p>
                    </div>
                    <div className="bg-white rounded-lg p-2.5">
                      <p className="text-xs text-gray-500">Result</p>
                      {onUpdateResult && examInfo.email ? (
                        <div className="flex gap-1.5 mt-0.5">
                          <button
                            onClick={() => onUpdateResult(examInfo.email, (examInfo.passFail || '').toUpperCase() === 'PASS' ? '' : 'PASS')}
                            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                              (examInfo.passFail || '').toUpperCase() === 'PASS'
                                ? 'bg-green-600 text-white shadow-sm'
                                : 'bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'
                            }`}
                          >
                            PASS
                          </button>
                          <button
                            onClick={() => onUpdateResult(examInfo.email, (examInfo.passFail || '').toUpperCase() === 'FAIL' ? '' : 'FAIL')}
                            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                              (examInfo.passFail || '').toUpperCase() === 'FAIL'
                                ? 'bg-red-600 text-white shadow-sm'
                                : 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
                            }`}
                          >
                            FAIL
                          </button>
                        </div>
                      ) : (
                        <p className="font-semibold text-sm">
                          {(examInfo.passFail || '').toUpperCase() === 'PASS' && <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded text-xs">PASS</span>}
                          {(examInfo.passFail || '').toUpperCase() === 'FAIL' && <span className="text-red-700 bg-red-100 px-2 py-0.5 rounded text-xs">FAIL</span>}
                          {!(examInfo.passFail || '').trim() && <span className="text-gray-500">Pending</span>}
                        </p>
                      )}
                    </div>
                  </div>
                  {(examInfo.departmentName || examInfo.agencyOwner) && (
                    <div className="grid grid-cols-2 gap-3 mt-3">
                      {examInfo.departmentName && (
                        <div className="bg-white rounded-lg p-2.5">
                          <p className="text-xs text-gray-500">Department</p>
                          <p className="font-semibold text-gray-900 text-sm">{examInfo.departmentName}</p>
                        </div>
                      )}
                      {examInfo.agencyOwner && (
                        <div className="bg-white rounded-lg p-2.5">
                          <p className="text-xs text-gray-500">Agency Owner</p>
                          <p className="font-semibold text-gray-900 text-sm">{examInfo.agencyOwner}</p>
                        </div>
                      )}
                    </div>
                  )}
                  {/* Admin Tracking Data */}
                  {examInfo.sheetTracking && (examInfo.sheetTracking.studyHoursAtExam || examInfo.sheetTracking.finalPractice) && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 pt-3 border-t border-blue-200">
                      {examInfo.sheetTracking.studyHoursAtExam && (
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-purple-700">{examInfo.sheetTracking.studyHoursAtExam}</p>
                          <p className="text-xs text-gray-500">Study Hours</p>
                        </div>
                      )}
                      {examInfo.sheetTracking.finalPractice && (
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-blue-700">{examInfo.sheetTracking.finalPractice}</p>
                          <p className="text-xs text-gray-500">Practice %</p>
                        </div>
                      )}
                      {examInfo.sheetTracking.chaptersComplete && (
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-green-700">{examInfo.sheetTracking.chaptersComplete}</p>
                          <p className="text-xs text-gray-500">Chapters</p>
                        </div>
                      )}
                      {examInfo.sheetTracking.studyConsistency && (
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-gray-700">{examInfo.sheetTracking.studyConsistency}</p>
                          <p className="text-xs text-gray-500">Consistency</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Readiness Breakdown */}
              {student.readiness && (
                <div className={`border-2 rounded-xl p-4 ${
                  student.readiness.status === 'GREEN' ? 'border-green-300 bg-green-50' :
                  student.readiness.status === 'YELLOW' ? 'border-yellow-300 bg-yellow-50' :
                  'border-red-300 bg-red-50'
                }`}>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-bold text-gray-900 flex items-center gap-2 text-sm">
                      <span className={`w-3 h-3 rounded-full ${
                        student.readiness.status === 'GREEN' ? 'bg-green-500' :
                        student.readiness.status === 'YELLOW' ? 'bg-yellow-400' :
                        'bg-red-500'
                      }`}></span>
                      Exam Readiness
                    </h4>
                    <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                      student.readiness.status === 'GREEN' ? 'bg-green-200 text-green-800' :
                      student.readiness.status === 'YELLOW' ? 'bg-yellow-200 text-yellow-800' :
                      'bg-red-200 text-red-800'
                    }`}>
                      {student.readiness.status} ({student.readiness.criteriaMet}/{student.readiness.criteriaTotal})
                    </span>
                  </div>
                  <div className="space-y-2">
                    {/* Practice Exams */}
                    {student.readiness.criteria.practiceExams && (
                      <div className="bg-white rounded-lg p-2.5">
                        <div className="flex items-center gap-2">
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                            student.readiness.criteria.practiceExams.met ? 'bg-green-500' : 'bg-red-400'
                          }`}>
                            {student.readiness.criteria.practiceExams.met ? (
                              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" /></svg>
                            ) : (
                              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M6 18L18 6M6 6l12 12" /></svg>
                            )}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900">Practice Exams</p>
                            <p className="text-xs text-gray-500">
                              {student.readiness.criteria.practiceExams.consecutivePassing}/3 consecutive passing
                              {' \u2022 '}{student.readiness.criteria.practiceExams.totalExams} exam{student.readiness.criteria.practiceExams.totalExams !== 1 ? 's' : ''} found
                              {' \u2022 '}{formatHours(student.readiness.criteria.practiceExams.hoursSpent)} total time
                            </p>
                          </div>
                        </div>
                        {/* Individual exam details */}
                        {student.readiness.criteria.practiceExams.details?.length > 0 && (
                          <div className="mt-2 ml-7 space-y-1">
                            {student.readiness.criteria.practiceExams.details.map((detail, i) => (
                              <div key={i} className="flex items-center gap-2 text-xs">
                                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${detail.score >= 80 ? 'bg-green-500' : 'bg-red-400'}`}></span>
                                <span className={`font-medium ${detail.score >= 80 ? 'text-green-700' : 'text-red-600'}`}>{Math.round(detail.score * 10) / 10}%</span>
                                <span className="text-gray-400">{detail.minutes}m</span>
                                <span className="text-gray-400 truncate" title={detail.name}>{detail.name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                    {/* Time in Course */}
                    {student.readiness.criteria.timeInCourse && (
                      <div className="flex items-center gap-2 bg-white rounded-lg p-2.5">
                        <span className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                          student.readiness.criteria.timeInCourse.met ? 'bg-green-500' : 'bg-red-400'
                        }`}>
                          {student.readiness.criteria.timeInCourse.met ? (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" /></svg>
                          ) : (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M6 18L18 6M6 6l12 12" /></svg>
                          )}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900">Time in Course</p>
                          <p className="text-xs text-gray-500">
                            {formatHours(student.readiness.criteria.timeInCourse.hoursLogged)} / {student.readiness.criteria.timeInCourse.hoursRequired}h required
                            ({student.readiness.criteria.timeInCourse.courseType})
                          </p>
                        </div>
                      </div>
                    )}
                    {/* State Laws */}
                    {student.readiness.criteria.stateLaws && (
                      <div className="flex items-center gap-2 bg-white rounded-lg p-2.5">
                        <span className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                          student.readiness.criteria.stateLaws.met ? 'bg-green-500' : 'bg-red-400'
                        }`}>
                          {student.readiness.criteria.stateLaws.met ? (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" /></svg>
                          ) : (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M6 18L18 6M6 6l12 12" /></svg>
                          )}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900">State Laws</p>
                          <p className="text-xs text-gray-500">
                            {student.readiness.criteria.stateLaws.completions} completion{student.readiness.criteria.stateLaws.completions !== 1 ? 's' : ''}, {formatHours(student.readiness.criteria.stateLaws.hoursSpent)} spent (need 1 completion + 1h 30m)
                          </p>
                        </div>
                      </div>
                    )}
                    {/* Videos */}
                    {student.readiness.criteria.videos && (
                      <div className="flex items-center gap-2 bg-white rounded-lg p-2.5">
                        <span className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                          student.readiness.criteria.videos.met ? 'bg-green-500' : 'bg-red-400'
                        }`}>
                          {student.readiness.criteria.videos.met ? (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" /></svg>
                          ) : (
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M6 18L18 6M6 6l12 12" /></svg>
                          )}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900">Videos</p>
                          <p className="text-xs text-gray-500">
                            {student.readiness.criteria.videos.details?.life && (
                              <span>Life: {student.readiness.criteria.videos.details.life.minutes}m/30m{student.readiness.criteria.videos.details.life.met ? ' \u2713' : ''} </span>
                            )}
                            {student.readiness.criteria.videos.details?.health && (
                              <span>Health: {student.readiness.criteria.videos.details.health.minutes}m/30m{student.readiness.criteria.videos.details.health.met ? ' \u2713' : ''}</span>
                            )}
                            {!student.readiness.criteria.videos.details?.life && !student.readiness.criteria.videos.details?.health && (
                              <span>{student.readiness.criteria.videos.totalCourses} video course{student.readiness.criteria.videos.totalCourses !== 1 ? 's' : ''}</span>
                            )}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Study Consistency / Gap Metrics */}
              {student.gapMetrics && student.gapMetrics.study_gap_count > 0 && (
                <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
                  <h4 className="font-bold text-gray-900 flex items-center gap-2 text-sm mb-3">
                    <svg className="w-4 h-4 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Study Consistency
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-white rounded-lg p-2.5 text-center">
                      <p className={`text-lg font-bold ${
                        student.gapMetrics.study_gap_count > 5 ? 'text-red-600' :
                        student.gapMetrics.study_gap_count > 2 ? 'text-orange-600' :
                        'text-green-600'
                      }`}>
                        {student.gapMetrics.study_gap_count}
                      </p>
                      <p className="text-xs text-gray-500">Study Gaps</p>
                    </div>
                    <div className="bg-white rounded-lg p-2.5 text-center">
                      <p className="text-lg font-bold text-gray-700">{student.gapMetrics.total_gap_days}</p>
                      <p className="text-xs text-gray-500">Total Gap Days</p>
                    </div>
                    <div className="bg-white rounded-lg p-2.5 text-center">
                      <p className={`text-lg font-bold ${
                        student.gapMetrics.largest_gap_days > 7 ? 'text-red-600' :
                        student.gapMetrics.largest_gap_days > 3 ? 'text-orange-600' :
                        'text-green-600'
                      }`}>
                        {student.gapMetrics.largest_gap_days}
                      </p>
                      <p className="text-xs text-gray-500">Largest Gap (days)</p>
                    </div>
                    <div className="bg-white rounded-lg p-2.5 text-center">
                      <p className="text-sm font-bold text-gray-700">
                        {student.gapMetrics.last_gap_date || 'N/A'}
                      </p>
                      <p className="text-xs text-gray-500">Last Gap Date</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Study History (from SQLite snapshots) */}
              {snapshots.length > 0 && (
                <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
                  <h4
                    className="font-bold text-gray-900 flex items-center gap-2 text-sm mb-3 cursor-pointer"
                    onClick={() => setSnapshotsExpanded(!snapshotsExpanded)}
                  >
                    <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Study History
                    <span className="text-xs font-normal text-gray-500 ml-1">({snapshots.length} snapshot{snapshots.length !== 1 ? 's' : ''})</span>
                    <svg className={`w-4 h-4 ml-auto text-gray-400 transition-transform ${snapshotsExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </h4>

                  {/* Summary: latest vs oldest comparison */}
                  {(() => {
                    const latest = snapshots[0]
                    const oldest = snapshots[snapshots.length - 1]
                    const timeDelta = latest.total_time_min - oldest.total_time_min
                    const progressDelta = latest.prelicense_progress - oldest.prelicense_progress

                    const formatMin = (m) => {
                      if (m >= 60) return `${Math.floor(m / 60)}h ${Math.round(m % 60)}m`
                      return `${Math.round(m)}m`
                    }

                    return (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-indigo-700">{formatMin(latest.total_time_min)}</p>
                          <p className="text-xs text-gray-500">Study Time</p>
                          {snapshots.length > 1 && timeDelta > 0 && (
                            <p className="text-xs text-green-600">+{formatMin(timeDelta)}</p>
                          )}
                        </div>
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-indigo-700">{latest.prelicense_progress}%</p>
                          <p className="text-xs text-gray-500">Pre-License</p>
                          {snapshots.length > 1 && progressDelta !== 0 && (
                            <p className={`text-xs ${progressDelta > 0 ? 'text-green-600' : 'text-red-500'}`}>
                              {progressDelta > 0 ? '+' : ''}{progressDelta.toFixed(1)}%
                            </p>
                          )}
                        </div>
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <p className="text-lg font-bold text-indigo-700">{latest.consecutive_passing}</p>
                          <p className="text-xs text-gray-500">Consec. Passing</p>
                        </div>
                        <div className="bg-white rounded-lg p-2.5 text-center">
                          <span className={`inline-block w-3 h-3 rounded-full mr-1 ${
                            latest.readiness === 'GREEN' ? 'bg-green-500' :
                            latest.readiness === 'YELLOW' ? 'bg-yellow-400' : 'bg-red-500'
                          }`}></span>
                          <span className="text-sm font-bold text-gray-700">{latest.criteria_met}</span>
                          <p className="text-xs text-gray-500">Readiness</p>
                        </div>
                      </div>
                    )
                  })()}

                  {/* Study time progression bar chart */}
                  {snapshots.length > 1 && (
                    <div className="bg-white rounded-lg p-3 mb-3">
                      <p className="text-xs font-medium text-gray-600 mb-2">Study Time Progression</p>
                      <div className="flex items-end gap-1" style={{ height: '48px' }}>
                        {(() => {
                          const reversed = [...snapshots].reverse()
                          const maxTime = Math.max(...reversed.map(s => s.total_time_min), 1)
                          return reversed.map((snap, i) => {
                            const pct = Math.max((snap.total_time_min / maxTime) * 100, 4)
                            const color = snap.readiness === 'GREEN' ? 'bg-green-400' :
                                          snap.readiness === 'YELLOW' ? 'bg-yellow-400' : 'bg-red-400'
                            return (
                              <div
                                key={snap.id || i}
                                className={`flex-1 rounded-t ${color} transition-all`}
                                style={{ height: `${pct}%`, minWidth: '4px', maxWidth: '24px' }}
                                title={`${new Date(snap.snapshot_time).toLocaleDateString()} - ${Math.round(snap.total_time_min)}min (${snap.readiness})`}
                              />
                            )
                          })
                        })()}
                      </div>
                      <div className="flex justify-between text-xs text-gray-400 mt-1">
                        <span>{new Date(snapshots[snapshots.length - 1].snapshot_time).toLocaleDateString()}</span>
                        <span>{new Date(snapshots[0].snapshot_time).toLocaleDateString()}</span>
                      </div>
                    </div>
                  )}

                  {/* Expanded: full snapshot table */}
                  {snapshotsExpanded && (
                    <div className="bg-white rounded-lg overflow-hidden">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-indigo-100 text-gray-600">
                            <th className="px-2 py-1.5 text-left">Date</th>
                            <th className="px-2 py-1.5 text-right">Time</th>
                            <th className="px-2 py-1.5 text-right">Progress</th>
                            <th className="px-2 py-1.5 text-right">Passing</th>
                            <th className="px-2 py-1.5 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {snapshots.map((snap, i) => (
                            <tr key={snap.id || i} className="hover:bg-gray-50">
                              <td className="px-2 py-1.5 text-gray-600">
                                {new Date(snap.snapshot_time).toLocaleDateString()} {new Date(snap.snapshot_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </td>
                              <td className="px-2 py-1.5 text-right font-medium">
                                {snap.total_time_min >= 60
                                  ? `${Math.floor(snap.total_time_min / 60)}h ${Math.round(snap.total_time_min % 60)}m`
                                  : `${Math.round(snap.total_time_min)}m`
                                }
                              </td>
                              <td className="px-2 py-1.5 text-right">{snap.prelicense_progress}%</td>
                              <td className="px-2 py-1.5 text-right">{snap.consecutive_passing}/3</td>
                              <td className="px-2 py-1.5 text-center">
                                <span className={`inline-block w-2.5 h-2.5 rounded-full ${
                                  snap.readiness === 'GREEN' ? 'bg-green-500' :
                                  snap.readiness === 'YELLOW' ? 'bg-yellow-400' : 'bg-red-500'
                                }`} title={`${snap.readiness} (${snap.criteria_met})`}></span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Last Login</p>
                  <p className="font-semibold text-gray-900">{student.lastLogin.relative}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Course Time</p>
                  <p className="font-semibold text-gray-900">{student.timeSpent.formatted}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Exam Prep Time</p>
                  <p className="font-semibold text-purple-700">{student.examPrepTime?.formatted || '0m'}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Total Study Time</p>
                  <p className="font-semibold text-gray-900">{
                    (() => {
                      const courseMin = student.timeSpent?.minutes || 0
                      const prepMin = student.examPrepTime?.minutes || 0
                      const total = courseMin + prepMin
                      if (total >= 60) return `${Math.floor(total / 60)}h ${total % 60}m`
                      return `${total}m`
                    })()
                  }</p>
                </div>
              </div>

              {/* Current Progress */}
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium text-gray-900">{student.courseName}</p>
                  <span className="text-sm text-gray-500">{student.enrollmentStatusText}</span>
                </div>
                <ProgressBar progress={student.progress} />
              </div>

              {/* Grouped Enrollments */}
              {student.enrollments && student.enrollments.length > 0 && (
                <EnrollmentGroups enrollments={student.enrollments} />
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button onClick={onClose} className="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default StudentModal
