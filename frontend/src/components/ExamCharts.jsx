import React from 'react'
import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'
import { Doughnut, Bar } from 'react-chartjs-2'

ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

function ExamCharts({ examSummary, students }) {
  // -- 1. Exam Results Doughnut --
  const resultsData = {
    labels: ['Passed', 'Failed', 'Upcoming', 'Pending'],
    datasets: [{
      data: [
        examSummary.passed,
        examSummary.failed,
        examSummary.upcoming,
        examSummary.noResult
      ],
      backgroundColor: ['#22c55e', '#ef4444', '#3b82f6', '#f97316'],
      borderColor: ['#ffffff', '#ffffff', '#ffffff', '#ffffff'],
      borderWidth: 2
    }]
  }

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: { padding: 15, usePointStyle: true, font: { size: 12 } }
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const total = ctx.dataset.data.reduce((a, b) => a + b, 0)
            const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0
            return `${ctx.label}: ${ctx.raw} (${pct}%)`
          }
        }
      }
    }
  }

  // -- 2. Pass Rate by Course Type Bar --
  const courseTypes = examSummary.courseTypes || {}
  const courseLabels = Object.keys(courseTypes).filter(k => k !== 'Unknown' && k)
  const coursePassRates = courseLabels.map(c => {
    const d = courseTypes[c]
    const taken = d.passed + d.failed
    return taken > 0 ? Math.round(d.passed / taken * 100) : 0
  })
  const courseTaken = courseLabels.map(c => {
    const d = courseTypes[c]
    return d.passed + d.failed
  })

  const courseBarData = {
    labels: courseLabels,
    datasets: [{
      label: 'Pass Rate %',
      data: coursePassRates,
      backgroundColor: coursePassRates.map(r => r >= 70 ? '#22c55e' : r >= 50 ? '#f97316' : '#ef4444'),
      borderRadius: 6
    }]
  }

  const courseBarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const idx = ctx.dataIndex
            return `Pass rate: ${ctx.raw}% (${courseTaken[idx]} taken)`
          }
        }
      }
    },
    scales: {
      y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
      x: { ticks: { font: { size: 11 } } }
    }
  }

  // -- 3. Study Time: Passed vs Failed Bar --
  const studyBarData = {
    labels: ['Passed', 'Failed', 'All Students'],
    datasets: [{
      label: 'Avg Study Time (minutes)',
      data: [
        examSummary.avgStudyPassed || 0,
        examSummary.avgStudyFailed || 0,
        examSummary.avgStudyTime || 0
      ],
      backgroundColor: ['#22c55e', '#ef4444', '#6366f1'],
      borderRadius: 6
    }]
  }

  const formatMinLabel = (mins) => {
    if (mins >= 60) return `${Math.floor(mins / 60)}h ${mins % 60}m`
    return `${mins}m`
  }

  const studyBarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `Avg: ${formatMinLabel(ctx.raw)}`
        }
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: { callback: v => formatMinLabel(v) }
      }
    }
  }

  // -- Quick Stats from student data --
  const matched = students.filter(s => s.matched !== false)
  const passedStudents = students.filter(s => (s.passFail || '').toUpperCase() === 'PASS')
  const failedStudents = students.filter(s => (s.passFail || '').toUpperCase() === 'FAIL')

  // Progress distribution of matched students
  const progressRanges = [
    { label: '0-25%', min: 0, max: 25, count: 0, color: '#ef4444' },
    { label: '26-50%', min: 26, max: 50, count: 0, color: '#f97316' },
    { label: '51-75%', min: 51, max: 75, count: 0, color: '#3b82f6' },
    { label: '76-100%', min: 76, max: 100, count: 0, color: '#22c55e' }
  ]
  matched.forEach(s => {
    const p = s.progress?.value || 0
    for (const r of progressRanges) {
      if (p >= r.min && p <= r.max) { r.count++; break }
    }
  })

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {/* Exam Results Distribution */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Exam Results</h3>
        <div className="h-64">
          <Doughnut data={resultsData} options={doughnutOptions} />
        </div>
      </div>

      {/* Pass Rate by Course */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Pass Rate by Course</h3>
        <div className="h-64">
          {courseLabels.length > 0 ? (
            <Bar data={courseBarData} options={courseBarOptions} />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400">No exam results yet</div>
          )}
        </div>
      </div>

      {/* Study Time Comparison */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Avg Study Time</h3>
        {(examSummary.avgStudyPassed > 0 || examSummary.avgStudyFailed > 0) ? (
          <div className="h-64">
            <Bar data={studyBarData} options={studyBarOptions} />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Fallback: show exam stats as quick stats */}
            <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="font-medium text-gray-900">Passed</span>
              </div>
              <span className="text-2xl font-bold text-green-600">{passedStudents.length}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <span className="font-medium text-gray-900">Failed</span>
              </div>
              <span className="text-2xl font-bold text-red-600">{failedStudents.length}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="font-medium text-gray-900">Tracked</span>
              </div>
              <span className="text-2xl font-bold text-blue-600">{matched.length}</span>
            </div>
            <p className="text-xs text-gray-400 text-center">Study time data available for students in your department</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default ExamCharts
