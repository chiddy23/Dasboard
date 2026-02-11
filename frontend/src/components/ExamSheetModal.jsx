import React, { useEffect, useState } from 'react'
import ProgressBar from './ProgressBar'
import StatusBadge from './StatusBadge'

function ExamSheetModal({ student, adminMode, onClose, onUpdateResult, onUpdateExamDate }) {
  const [editingDate, setEditingDate] = useState(false)
  const [newDate, setNewDate] = useState('')
  const [newTime, setNewTime] = useState('')

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

  const hasPassed = (student.passFail || '').toUpperCase() === 'PASS'
  const hasFailed = (student.passFail || '').toUpperCase() === 'FAIL'
  const tracking = student.sheetTracking || {}

  // Status color helper for weekly tracking
  const getStatusColor = (status) => {
    const s = (status || '').toUpperCase()
    if (s === 'GREEN') return 'bg-green-100 text-green-700'
    if (s === 'YELLOW') return 'bg-yellow-100 text-yellow-700'
    if (s === 'RED') return 'bg-red-100 text-red-700'
    return 'bg-gray-100 text-gray-600'
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={`${adminMode ? 'bg-gradient-to-r from-purple-700 to-purple-900' : 'header'} px-6 py-4 rounded-t-xl`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-white">Student Details</h2>
              {adminMode && (
                <span className="px-2 py-0.5 bg-white/20 rounded text-xs text-white font-medium">Admin</span>
              )}
            </div>
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
        <div className="p-6 max-h-[80vh] overflow-y-auto">
          <div className="space-y-6">
            {/* Student Info */}
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-2xl font-bold text-gray-900">{student.fullName}</h3>
                <p className="text-gray-500">{student.email}</p>
                {adminMode && tracking.phone && (
                  <p className="text-gray-500 text-sm">{tracking.phone}</p>
                )}
              </div>
              {student.matched !== false ? (
                <StatusBadge status={student.status} />
              ) : (
                !adminMode && <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600">Not in department</span>
              )}
            </div>

            {/* Exam Info Card */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
              <h4 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Exam Information
                {onUpdateExamDate && !editingDate && (
                  <button
                    onClick={() => {
                      setEditingDate(true)
                      setNewDate(student.examDateRaw || '')
                      setNewTime(student.examTime || '')
                    }}
                    className="ml-auto text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                  >
                    Edit Date
                  </button>
                )}
              </h4>
              <div className="grid grid-cols-2 gap-4">
                {editingDate && onUpdateExamDate ? (
                  <>
                    <div className="bg-white rounded-lg p-3">
                      <p className="text-sm text-gray-500 mb-1">Exam Date</p>
                      <input
                        type="date"
                        value={newDate}
                        onChange={(e) => setNewDate(e.target.value)}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <p className="text-sm text-gray-500 mb-1">Exam Time</p>
                      <input
                        type="text"
                        value={newTime}
                        onChange={(e) => setNewTime(e.target.value)}
                        placeholder="e.g., 2:00 PM"
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div className="col-span-2 flex gap-2 justify-end">
                      <button
                        onClick={() => {
                          if (newDate) {
                            onUpdateExamDate(student.email, newDate, newTime)
                            setEditingDate(false)
                          }
                        }}
                        className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 transition-colors"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingDate(false)}
                        className="px-3 py-1 bg-gray-200 text-gray-700 rounded text-sm hover:bg-gray-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="bg-white rounded-lg p-3">
                      <p className="text-sm text-gray-500">Exam Date</p>
                      <p className="font-semibold text-gray-900">{student.examDate || 'TBD'}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3">
                      <p className="text-sm text-gray-500">Exam Time</p>
                      <p className="font-semibold text-gray-900">{student.examTime || 'N/A'}</p>
                    </div>
                  </>
                )}
                <div className="bg-white rounded-lg p-3">
                  <p className="text-sm text-gray-500">State</p>
                  <p className="font-semibold text-gray-900">{student.examState || 'N/A'}</p>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <p className="text-sm text-gray-500">Result</p>
                  {onUpdateResult ? (
                    <div className="flex gap-2 mt-1">
                      <button
                        onClick={() => onUpdateResult(student.email, hasPassed ? '' : 'PASS')}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          hasPassed
                            ? 'bg-green-600 text-white shadow-sm'
                            : 'bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'
                        }`}
                      >
                        PASS
                      </button>
                      <button
                        onClick={() => onUpdateResult(student.email, hasFailed ? '' : 'FAIL')}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          hasFailed
                            ? 'bg-red-600 text-white shadow-sm'
                            : 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
                        }`}
                      >
                        FAIL
                      </button>
                    </div>
                  ) : (
                    <p className="font-semibold">
                      {hasPassed && <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded">PASS</span>}
                      {hasFailed && <span className="text-red-700 bg-red-100 px-2 py-0.5 rounded">FAIL</span>}
                      {!hasPassed && !hasFailed && <span className="text-gray-600">Pending</span>}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Course & Agency Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-500">Course</p>
                <p className="font-semibold text-gray-900">{student.examCourse || student.courseName || 'N/A'}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-500">Agency Owner</p>
                <p className="font-semibold text-gray-900">{student.agencyOwner || 'N/A'}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-500">Department</p>
                <p className="font-semibold text-gray-900">{student.departmentName || 'N/A'}</p>
              </div>
              {student.finalOutcome && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Final Outcome</p>
                  <p className="font-semibold text-gray-900">{student.finalOutcome}</p>
                </div>
              )}
            </div>

            {/* Admin: Study Stats at Exam */}
            {adminMode && (tracking.studyHoursAtExam || tracking.finalPractice || tracking.chaptersComplete) && (
              <div className="bg-purple-50 border border-purple-200 rounded-xl p-5">
                <h4 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  Study Stats at Exam
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {tracking.studyHoursAtExam && (
                    <div className="bg-white rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-purple-700">{tracking.studyHoursAtExam}</p>
                      <p className="text-xs text-gray-500">Study Hours</p>
                    </div>
                  )}
                  {tracking.finalPractice && (
                    <div className="bg-white rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-blue-700">{tracking.finalPractice}</p>
                      <p className="text-xs text-gray-500">Final Practice %</p>
                    </div>
                  )}
                  {tracking.chaptersComplete && (
                    <div className="bg-white rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-green-700">{tracking.chaptersComplete}</p>
                      <p className="text-xs text-gray-500">Chapters Complete</p>
                    </div>
                  )}
                  {tracking.videosWatched && (
                    <div className="bg-white rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-indigo-700">{tracking.videosWatched}</p>
                      <p className="text-xs text-gray-500">Videos Watched</p>
                    </div>
                  )}
                  {tracking.stateLawsDone && (
                    <div className="bg-white rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-amber-700">{tracking.stateLawsDone}</p>
                      <p className="text-xs text-gray-500">State Laws Done</p>
                    </div>
                  )}
                  {tracking.studyConsistency && (
                    <div className="bg-white rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-gray-700">{tracking.studyConsistency}</p>
                      <p className="text-xs text-gray-500">Study Consistency</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Admin: Weekly Tracking Timeline */}
            {adminMode && tracking.weeklyTracking && tracking.weeklyTracking.length > 0 && (
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-5">
                <h4 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Weekly Tracking
                  {tracking.t0Sent && <span className="text-xs font-normal text-gray-500 ml-2">T-0 Sent: {tracking.t0Sent}</span>}
                </h4>
                <div className="space-y-3">
                  {tracking.weeklyTracking.map((week) => (
                    <div key={week.week} className="bg-white rounded-lg p-3 flex items-center gap-4">
                      <div className="w-12 text-center">
                        <span className="font-bold text-gray-700 text-sm">{week.week}</span>
                      </div>
                      <div className="flex-1 flex items-center gap-3 flex-wrap">
                        {week.status && (
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(week.status)}`}>
                            {week.status}
                          </span>
                        )}
                        {week.hours && (
                          <span className="text-sm text-gray-700">
                            <span className="text-gray-500">Hours:</span> {week.hours}
                          </span>
                        )}
                        {week.practice && (
                          <span className="text-sm text-gray-700">
                            <span className="text-gray-500">Practice:</span> {week.practice}
                          </span>
                        )}
                      </div>
                      {week.notes && (
                        <p className="text-xs text-gray-500 italic max-w-[200px] truncate" title={week.notes}>
                          {week.notes}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Progress section (if matched with Absorb) */}
            {student.matched !== false && (
              <>
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-medium text-gray-900">{student.courseName}</p>
                  </div>
                  <ProgressBar progress={student.progress} />
                  <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                    <span>Course: {student.timeSpent?.formatted || '0m'}</span>
                    {student.examPrepTime?.minutes > 0 && (
                      <span className="text-purple-600">Prep: {student.examPrepTime.formatted}</span>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* Note for unmatched students (only show when NOT in admin mode) */}
            {student.matched === false && !adminMode && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
                <svg className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="font-medium text-amber-800">Student not in your department</p>
                  <p className="text-sm text-amber-700 mt-1">Course progress and study time data from Absorb is only available for students in your department. Log in as their department admin to see full details.</p>
                </div>
              </div>
            )}
          </div>
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

export default ExamSheetModal
