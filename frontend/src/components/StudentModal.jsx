import React, { useState, useEffect, useMemo } from 'react'
import StatusBadge from './StatusBadge'
import ProgressBar from './ProgressBar'

const API_BASE = '/api'

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

function StudentModal({ studentId, examInfo, onClose, onSessionExpired, onUpdateResult, onUpdateExamDate }) {
  const [student, setStudent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingDate, setEditingDate] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [newTime, setNewTime] = useState('')

  useEffect(() => {
    fetchStudentDetails()
  }, [studentId])

  const fetchStudentDetails = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/students/${studentId}`, {
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
      } else {
        throw new Error(data.error || 'Failed to load student')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
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
                <div>
                  <h3 className="text-2xl font-bold text-gray-900">{student.fullName}</h3>
                  <p className="text-gray-500">{student.email}</p>
                </div>
                <StatusBadge status={student.status} />
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
                        className="ml-auto text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                      >
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
