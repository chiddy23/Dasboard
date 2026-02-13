import React, { useState, useMemo } from 'react'
import StatusBadge from './StatusBadge'
import ProgressBar from './ProgressBar'

function ExamTable({ students, onViewStudent, adminMode }) {
  const [sortField, setSortField] = useState('examDate')
  const [sortDirection, setSortDirection] = useState('asc')

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const parseExamDate = (dateStr) => {
    if (!dateStr) return 0
    const formats = [
      // "Jan 9, 2026" format (backend formatted)
      (s) => new Date(s),
      // "1/9/2026" format (raw)
      (s) => {
        const parts = s.split('/')
        if (parts.length === 3) {
          return new Date(parts[2], parts[0] - 1, parts[1])
        }
        return new Date(0)
      }
    ]
    for (const parse of formats) {
      try {
        const d = parse(dateStr)
        if (!isNaN(d.getTime())) return d.getTime()
      } catch (e) { /* continue */ }
    }
    return 0
  }

  const sortedStudents = useMemo(() => {
    const arr = [...students]
    arr.sort((a, b) => {
      let aValue, bValue

      switch (sortField) {
        case 'name':
          aValue = (a.fullName || '').toLowerCase()
          bValue = (b.fullName || '').toLowerCase()
          break
        case 'status':
          aValue = a.status?.priority ?? 99
          bValue = b.status?.priority ?? 99
          break
        case 'examDate':
          aValue = parseExamDate(a.examDateRaw || a.examDate)
          bValue = parseExamDate(b.examDateRaw || b.examDate)
          break
        case 'department':
          aValue = (a.departmentName || '').toLowerCase()
          bValue = (b.departmentName || '').toLowerCase()
          break
        case 'progress':
          aValue = a.progress?.value ?? 0
          bValue = b.progress?.value ?? 0
          break
        case 'result':
          // PASS=1 (top), FAIL=2, no result=3
          aValue = (a.passFail || '').toUpperCase() === 'PASS' ? 1 : (a.passFail || '').toUpperCase() === 'FAIL' ? 2 : 3
          bValue = (b.passFail || '').toUpperCase() === 'PASS' ? 1 : (b.passFail || '').toUpperCase() === 'FAIL' ? 2 : 3
          break
        case 'state':
          aValue = (a.examState || '').toLowerCase()
          bValue = (b.examState || '').toLowerCase()
          break
        case 'course':
          aValue = (a.courseName || '').toLowerCase()
          bValue = (b.courseName || '').toLowerCase()
          break
        default:
          aValue = parseExamDate(a.examDateRaw || a.examDate)
          bValue = parseExamDate(b.examDateRaw || b.examDate)
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1
      return 0
    })
    return arr
  }, [students, sortField, sortDirection])

  const SortIcon = ({ field }) => {
    if (sortField !== field) {
      return (
        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      )
    }
    return sortDirection === 'asc' ? (
      <svg className="w-4 h-4 text-ji-blue-bright" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
      </svg>
    ) : (
      <svg className="w-4 h-4 text-ji-blue-bright" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
      </svg>
    )
  }

  // Check if exam date is in the past
  const isExamPast = (dateStr) => {
    const ts = parseExamDate(dateStr)
    if (!ts) return false
    const examDate = new Date(ts)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return examDate < today
  }

  // Compute readiness color for a student (uses backend readiness calculator when available)
  const getReadiness = (student) => {
    const pf = (student.passFail || '').toUpperCase()
    if (pf === 'PASS') return 'green'
    if (pf === 'FAIL') return 'red'
    // Use backend readiness if available
    if (student.readiness?.status) {
      return student.readiness.status.toLowerCase()
    }
    // Fallback for unmatched students without readiness data
    return 'red'
  }

  if (students.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-md p-8 text-center">
        <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <h3 className="text-lg font-medium text-gray-600 mb-2">No exam students found</h3>
        <p className="text-gray-500">No students with scheduled exams</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden">
      {/* Scroll hint */}
      <div className="bg-blue-50 border-b border-blue-100 px-4 py-2 text-xs text-blue-700 flex items-center gap-2">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Scroll horizontally to see all columns {'\u2022'} Click "View" to edit exam dates</span>
      </div>
      <div className="table-scroll-wrapper">
        <table className="data-table min-w-full">
          <thead>
            <tr>
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[200px]"
                onClick={() => handleSort('name')}
              >
                <div className="flex items-center space-x-1">
                  <span>Student</span>
                  <SortIcon field="name" />
                </div>
              </th>
              {adminMode && (
                <th
                  className="cursor-pointer hover:bg-gray-100 min-w-[130px]"
                  onClick={() => handleSort('department')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Department</span>
                    <SortIcon field="department" />
                  </div>
                </th>
              )}
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[100px]"
                onClick={() => handleSort('status')}
              >
                <div className="flex items-center space-x-1">
                  <span>Status</span>
                  <SortIcon field="status" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[120px]"
                onClick={() => handleSort('examDate')}
              >
                <div className="flex items-center space-x-1">
                  <span>Exam Date</span>
                  <SortIcon field="examDate" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[200px]"
                onClick={() => handleSort('progress')}
              >
                <div className="flex items-center space-x-1">
                  <span>Progress</span>
                  <SortIcon field="progress" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[180px]"
                onClick={() => handleSort('course')}
              >
                <div className="flex items-center space-x-1">
                  <span>Course</span>
                  <SortIcon field="course" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[80px]"
                onClick={() => handleSort('result')}
              >
                <div className="flex items-center space-x-1">
                  <span>Result</span>
                  <SortIcon field="result" />
                </div>
              </th>
              {!adminMode && (
                <th
                  className="cursor-pointer hover:bg-gray-100 min-w-[130px]"
                  onClick={() => handleSort('department')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Department</span>
                    <SortIcon field="department" />
                  </div>
                </th>
              )}
              <th
                className="cursor-pointer hover:bg-gray-100 min-w-[70px]"
                onClick={() => handleSort('state')}
              >
                <div className="flex items-center space-x-1">
                  <span>State</span>
                  <SortIcon field="state" />
                </div>
              </th>
              <th className="sticky right-0 bg-gray-50 min-w-[80px] whitespace-nowrap">Action</th>
            </tr>
          </thead>
          <tbody>
            {sortedStudents.map((student, index) => {
              const past = isExamPast(student.examDateRaw || student.examDate)
              const hasPassed = student.passFail?.toUpperCase() === 'PASS'
              const hasFailed = student.passFail?.toUpperCase() === 'FAIL'
              const readiness = getReadiness(student)
              const readinessColor = readiness === 'green' ? 'bg-green-500' : readiness === 'yellow' ? 'bg-yellow-400' : 'bg-red-500'

              return (
                <tr
                  key={`${student.email}-${student.examDateRaw || index}`}
                  className="animate-fadeIn"
                  style={{ animationDelay: `${index * 20}ms` }}
                >
                  <td>
                    <div className="flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${readinessColor}`} title={`Readiness: ${readiness}`}></span>
                      <div>
                        <p className="font-medium text-gray-900">{student.fullName}</p>
                        <p className="text-sm text-gray-500">{student.email}</p>
                      </div>
                    </div>
                  </td>
                  {adminMode && (
                    <td>
                      <p className="text-gray-900 text-sm" title={student.departmentName}>
                        {student.departmentName || 'Unknown'}
                      </p>
                    </td>
                  )}
                  <td>
                    {student.matched !== false ? (
                      <StatusBadge status={student.status} />
                    ) : (
                      <span className="badge bg-gray-100 text-gray-600">N/A</span>
                    )}
                  </td>
                  <td>
                    <div>
                      <p className={`font-medium ${past ? 'text-gray-500' : 'text-gray-900'}`}>
                        {student.examDate || 'TBD'}
                      </p>
                      {student.examTime && (
                        <p className="text-xs text-gray-500">{student.examTime}</p>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="min-w-[180px]">
                      <ProgressBar progress={student.progress} />
                      <p className="text-xs text-gray-500 mt-1">Course: {student.timeSpent?.formatted || '0m'}</p>
                      {student.examPrepTime?.minutes > 0 && (
                        <p className="text-xs text-purple-500">Prep: {student.examPrepTime.formatted}</p>
                      )}
                    </div>
                  </td>
                  <td>
                    <p className="text-gray-900 text-sm" title={student.courseName}>
                      {student.courseName}
                    </p>
                  </td>
                  <td>
                    {hasPassed ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-sm font-bold bg-green-100 text-green-800 border border-green-300">
                        PASS
                      </span>
                    ) : hasFailed ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-sm font-bold bg-red-100 text-red-800 border border-red-300">
                        FAIL
                      </span>
                    ) : (
                      <span className="text-gray-400 text-sm">{'\u2014'}</span>
                    )}
                  </td>
                  {!adminMode && (
                    <td>
                      <p className="text-gray-900 text-sm" title={student.departmentName}>
                        {student.departmentName || 'Unknown'}
                      </p>
                    </td>
                  )}
                  <td>
                    <p className="text-gray-900 text-sm">{student.examState || '\u2014'}</p>
                  </td>
                  <td className="sticky right-0 bg-white">
                    <button
                      onClick={() => onViewStudent(student)}
                      className="btn btn-secondary text-sm py-1 px-3 whitespace-nowrap"
                    >
                      View
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ExamTable
