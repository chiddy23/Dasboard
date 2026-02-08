import React, { useEffect } from 'react'
import ProgressBar from './ProgressBar'
import StatusBadge from './StatusBadge'

function ExamSheetModal({ student, onClose }) {
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
          <div className="space-y-6">
            {/* Student Info */}
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-2xl font-bold text-gray-900">{student.fullName}</h3>
                <p className="text-gray-500">{student.email}</p>
              </div>
              {student.matched !== false ? (
                <StatusBadge status={student.status} />
              ) : (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600">Not in department</span>
              )}
            </div>

            {/* Exam Info Card */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
              <h4 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Exam Information
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-lg p-3">
                  <p className="text-sm text-gray-500">Exam Date</p>
                  <p className="font-semibold text-gray-900">{student.examDate || 'TBD'}</p>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <p className="text-sm text-gray-500">Exam Time</p>
                  <p className="font-semibold text-gray-900">{student.examTime || 'N/A'}</p>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <p className="text-sm text-gray-500">State</p>
                  <p className="font-semibold text-gray-900">{student.examState || 'N/A'}</p>
                </div>
                <div className="bg-white rounded-lg p-3">
                  <p className="text-sm text-gray-500">Result</p>
                  <p className="font-semibold">
                    {hasPassed && <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded">PASS</span>}
                    {hasFailed && <span className="text-red-700 bg-red-100 px-2 py-0.5 rounded">FAIL</span>}
                    {!hasPassed && !hasFailed && <span className="text-gray-600">Pending</span>}
                  </p>
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

            {/* Note for unmatched students */}
            {student.matched === false && (
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
