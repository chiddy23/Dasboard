import React, { useState } from 'react'
import StatusBadge from './StatusBadge'
import ProgressBar from './ProgressBar'

function StudentTable({ students, onViewStudent, showDepartment = false, onHideStudent, showHidden = false }) {
  const [sortField, setSortField] = useState('status')
  const [sortDirection, setSortDirection] = useState('asc')

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const sortedStudents = [...students].sort((a, b) => {
    let aValue, bValue

    switch (sortField) {
      case 'name':
        aValue = a.fullName.toLowerCase()
        bValue = b.fullName.toLowerCase()
        break
      case 'status':
        aValue = a.status.priority
        bValue = b.status.priority
        break
      case 'lastLogin':
        aValue = a.lastLogin.raw ? new Date(a.lastLogin.raw).getTime() : 0
        bValue = b.lastLogin.raw ? new Date(b.lastLogin.raw).getTime() : 0
        break
      case 'progress':
        aValue = a.progress.value
        bValue = b.progress.value
        break
      case 'course':
        aValue = a.courseName.toLowerCase()
        bValue = b.courseName.toLowerCase()
        break
      case 'department':
        aValue = (a.departmentName || '').toLowerCase()
        bValue = (b.departmentName || '').toLowerCase()
        break
      default:
        aValue = a.status.priority
        bValue = b.status.priority
    }

    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1
    return 0
  })

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

  if (students.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-md p-8 text-center">
        <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
        <h3 className="text-lg font-medium text-gray-600 mb-2">No students found</h3>
        <p className="text-gray-500">Try adjusting your search or filter criteria</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('name')}
              >
                <div className="flex items-center space-x-1">
                  <span>Student</span>
                  <SortIcon field="name" />
                </div>
              </th>
              {showDepartment && (
                <th
                  className="cursor-pointer hover:bg-gray-100 hidden lg:table-cell"
                  onClick={() => handleSort('department')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Dept</span>
                    <SortIcon field="department" />
                  </div>
                </th>
              )}
              <th
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('status')}
              >
                <div className="flex items-center space-x-1">
                  <span>Status</span>
                  <SortIcon field="status" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('lastLogin')}
              >
                <div className="flex items-center space-x-1">
                  <span>Last Login</span>
                  <SortIcon field="lastLogin" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100 hidden md:table-cell"
                onClick={() => handleSort('course')}
              >
                <div className="flex items-center space-x-1">
                  <span>Course</span>
                  <SortIcon field="course" />
                </div>
              </th>
              <th
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('progress')}
              >
                <div className="flex items-center space-x-1">
                  <span>Progress</span>
                  <SortIcon field="progress" />
                </div>
              </th>
              <th className="sticky right-0 bg-gray-50 min-w-[80px] whitespace-nowrap">Action</th>
            </tr>
          </thead>
          <tbody>
            {sortedStudents.map((student, index) => (
              <tr
                key={student.id || `${student.email}-${index}`}
                className="animate-fadeIn"
                style={{ animationDelay: `${index * 20}ms` }}
              >
                <td>
                  <div>
                    <p className="font-medium text-gray-900">{student.fullName}</p>
                    <p className="text-sm text-gray-500">{student.email}</p>
                  </div>
                </td>
                {showDepartment && (
                  <td className="hidden lg:table-cell">
                    <p className="text-gray-700 text-sm truncate max-w-[220px]" title={student.departmentName || ''}>
                      {student.departmentName || '-'}
                    </p>
                  </td>
                )}
                <td>
                  <StatusBadge status={student.status} />
                </td>
                <td>
                  <div>
                    <p className="text-gray-900">{student.lastLogin.relative}</p>
                    <p className="text-xs text-gray-500 hidden sm:block">{student.lastLogin.formatted}</p>
                  </div>
                </td>
                <td className="hidden md:table-cell">
                  <p className="text-gray-900 truncate max-w-sm" title={student.courseName}>
                    {student.courseName}
                  </p>
                </td>
                <td>
                  <div className="w-36">
                    <ProgressBar progress={student.progress} />
                    <p className="text-xs text-gray-500 mt-1">Course: {student.timeSpent?.formatted || '0m'}</p>
                    {student.examPrepTime?.minutes > 0 && (
                      <p className="text-xs text-purple-500">Prep: {student.examPrepTime.formatted}</p>
                    )}
                  </div>
                </td>
                <td className="sticky right-0 bg-white">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onViewStudent(student)}
                      className="btn btn-secondary text-sm py-1 px-3 whitespace-nowrap"
                    >
                      View
                    </button>
                    {onHideStudent && (
                      <button
                        onClick={() => onHideStudent(student.email)}
                        className={`p-1.5 rounded transition-colors ${
                          showHidden
                            ? 'text-green-600 hover:bg-green-50'
                            : 'text-gray-400 hover:text-red-500 hover:bg-red-50'
                        }`}
                        title={showHidden ? 'Unhide student' : 'Hide student'}
                      >
                        {showHidden ? (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default StudentTable
