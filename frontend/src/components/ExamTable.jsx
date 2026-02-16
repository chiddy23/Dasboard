import React, { useState } from 'react'
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

  // Parse exam date to LOCAL midnight timestamp, handling all formats
  const parseExamDate = (dateStr) => {
    if (!dateStr) return 0
    const str = dateStr.trim()

    // Try M/D/YYYY or M/D/YY (from Google Sheet CSV) - parse explicitly to avoid timezone issues
    const slashParts = str.split('/')
    if (slashParts.length === 3) {
      let year = parseInt(slashParts[2], 10)
      if (year < 100) year += 2000 // 2-digit year fix
      const d = new Date(year, parseInt(slashParts[0], 10) - 1, parseInt(slashParts[1], 10))
      if (!isNaN(d.getTime())) return d.getTime()
    }

    // Try YYYY-MM-DD (from date overrides) - parse as LOCAL, not UTC
    const isoParts = str.match(/^(\d{4})-(\d{2})-(\d{2})$/)
    if (isoParts) {
      const d = new Date(parseInt(isoParts[1], 10), parseInt(isoParts[2], 10) - 1, parseInt(isoParts[3], 10))
      if (!isNaN(d.getTime())) return d.getTime()
    }

    // Fallback: "Feb 17, 2026" or other text format - force to local midnight
    const d = new Date(str)
    if (!isNaN(d.getTime())) {
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
    }

    return 0
  }

  // Classify a student's exam date relative to today
  const getDateGroup = (student) => {
    const ts = parseExamDate(student.examDateRaw || student.examDate)
    if (!ts) return 'upcoming' // No date = treat as upcoming/TBD

    const examDate = new Date(ts)
    const today = new Date()

    // Compare year/month/day directly to avoid any timezone/millisecond issues
    const ey = examDate.getFullYear(), em = examDate.getMonth(), ed = examDate.getDate()
    const ty = today.getFullYear(), tm = today.getMonth(), td = today.getDate()

    if (ey === ty && em === tm && ed === td) return 'today'
    if (new Date(ey, em, ed) > new Date(ty, tm, td)) return 'upcoming'
    return 'past'
  }

  // Sort students within a group by the chosen field
  const sortWithinGroup = (list) => {
    return [...list].sort((a, b) => {
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
          // PASS=1 (top), No result=2 (middle), FAIL=3 (bottom)
          aValue = (a.passFail || '').toUpperCase() === 'PASS' ? 1 : (a.passFail || '').toUpperCase() === 'FAIL' ? 3 : 2
          bValue = (b.passFail || '').toUpperCase() === 'PASS' ? 1 : (b.passFail || '').toUpperCase() === 'FAIL' ? 3 : 2
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
  }

  // Group students into today / upcoming / past
  const todayStudents = students.filter(s => getDateGroup(s) === 'today')
  const upcomingStudents = students.filter(s => getDateGroup(s) === 'upcoming')
  const pastStudents = students.filter(s => getDateGroup(s) === 'past')

  // Sort within each group
  const sortedToday = sortWithinGroup(todayStudents)
  const sortedUpcoming = sortWithinGroup(upcomingStudents)
  // Past: default to most recent first (desc date) unless user explicitly sorts
  const sortedPast = sortField === 'examDate'
    ? [...pastStudents].sort((a, b) => {
        const aTs = parseExamDate(a.examDateRaw || a.examDate)
        const bTs = parseExamDate(b.examDateRaw || b.examDate)
        // Most recent past date first
        return sortDirection === 'asc' ? bTs - aTs : aTs - bTs
      })
    : sortWithinGroup(pastStudents)

  // Build ordered sections: Today > Upcoming > Past
  const sections = []
  if (sortedToday.length > 0) {
    sections.push({ label: `Today's Exams`, color: 'blue', icon: 'calendar-today', students: sortedToday })
  }
  if (sortedUpcoming.length > 0) {
    sections.push({ label: 'Upcoming Exams', color: 'green', icon: 'calendar-upcoming', students: sortedUpcoming })
  }
  if (sortedPast.length > 0) {
    sections.push({ label: 'Past Exams', color: 'gray', icon: 'calendar-past', students: sortedPast })
  }

  const totalColumns = adminMode ? 9 : 9 // Student, (Dept admin), Status, Date, Progress, Course, Result, (Dept non-admin), State, Action

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

  // Compute dot color for a student (based on pass/fail result only)
  // Study readiness details are available in the student modal
  const getReadiness = (student) => {
    const pf = (student.passFail || '').toUpperCase()
    if (pf === 'PASS') return 'green'
    if (pf === 'FAIL') return 'red'
    // No exam result yet = neutral gray dot (avoids confusion with FAIL)
    return 'gray'
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

  // Render a student row
  const renderStudentRow = (student, index, sectionIndex) => {
    const past = isExamPast(student.examDateRaw || student.examDate)
    const hasPassed = student.passFail?.toUpperCase() === 'PASS'
    const hasFailed = student.passFail?.toUpperCase() === 'FAIL'
    const readiness = getReadiness(student)
    const readinessColor = readiness === 'green' ? 'bg-green-500' : readiness === 'yellow' ? 'bg-yellow-400' : readiness === 'gray' ? 'bg-gray-300' : 'bg-red-500'
    const isToday = getDateGroup(student) === 'today'

    return (
      <tr
        key={`${student.email}-${student.examDateRaw || index}`}
        className={`animate-fadeIn ${isToday ? 'bg-blue-50/40' : ''}`}
        style={{ animationDelay: `${(sectionIndex + index) * 20}ms` }}
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
            <p className={`font-medium ${past ? 'text-gray-400' : isToday ? 'text-blue-700 font-semibold' : 'text-gray-900'}`}>
              {student.examDate || 'TBD'}
              {isToday && <span className="ml-1.5 text-xs font-medium text-blue-500">TODAY</span>}
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
  }

  // Section divider colors
  const sectionColors = {
    blue: { bg: 'bg-blue-600', text: 'text-white', border: 'border-blue-700' },
    green: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    gray: { bg: 'bg-gray-100', text: 'text-gray-500', border: 'border-gray-200' }
  }

  let runningIndex = 0

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
            {sections.map((section, sectionIdx) => {
              const colors = sectionColors[section.color]
              const sectionStartIndex = runningIndex
              runningIndex += section.students.length

              return (
                <React.Fragment key={section.label}>
                  {/* Section divider row */}
                  <tr>
                    <td
                      colSpan={totalColumns}
                      className={`${colors.bg} ${colors.text} ${colors.border} border-y px-4 py-2`}
                    >
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        {section.color === 'blue' && (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        )}
                        {section.color === 'green' && (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        )}
                        {section.color === 'gray' && (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        )}
                        <span>{section.label}</span>
                        <span className={`text-xs font-normal ${section.color === 'blue' ? 'text-blue-200' : 'opacity-60'}`}>
                          ({section.students.length} student{section.students.length !== 1 ? 's' : ''})
                        </span>
                      </div>
                    </td>
                  </tr>
                  {/* Student rows for this section */}
                  {section.students.map((student, idx) =>
                    renderStudentRow(student, idx, sectionStartIndex)
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ExamTable
