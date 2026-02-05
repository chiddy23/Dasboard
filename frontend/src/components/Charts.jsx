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

// Register Chart.js components
ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

function Charts({ summary, students }) {
  // Status Distribution Doughnut Chart
  const statusData = {
    labels: ['Active', 'Warning', 'Re-engage'],
    datasets: [
      {
        data: [summary.activeCount, summary.warningCount, summary.reengageCount],
        backgroundColor: ['#22c55e', '#f97316', '#ef4444'],
        borderColor: ['#ffffff', '#ffffff', '#ffffff'],
        borderWidth: 2
      }
    ]
  }

  const statusOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          padding: 20,
          usePointStyle: true,
          font: {
            size: 12
          }
        }
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            const total = context.dataset.data.reduce((a, b) => a + b, 0)
            const percentage = ((context.raw / total) * 100).toFixed(1)
            return `${context.label}: ${context.raw} (${percentage}%)`
          }
        }
      }
    }
  }

  // Progress Distribution Bar Chart
  const progressRanges = [
    { label: '0-25%', min: 0, max: 25, count: 0, color: '#ef4444' },
    { label: '26-50%', min: 26, max: 50, count: 0, color: '#f97316' },
    { label: '51-75%', min: 51, max: 75, count: 0, color: '#3b82f6' },
    { label: '76-100%', min: 76, max: 100, count: 0, color: '#22c55e' }
  ]

  students.forEach(student => {
    const progress = student.progress.value
    for (const range of progressRanges) {
      if (progress >= range.min && progress <= range.max) {
        range.count++
        break
      }
    }
  })

  const progressData = {
    labels: progressRanges.map(r => r.label),
    datasets: [
      {
        label: 'Students',
        data: progressRanges.map(r => r.count),
        backgroundColor: progressRanges.map(r => r.color),
        borderRadius: 6
      }
    ]
  }

  const progressOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.raw} students`
        }
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          stepSize: 1
        }
      }
    }
  }

  // Calculate additional stats
  const completedCount = students.filter(s => s.enrollmentStatus === 2).length
  const inProgressCount = students.filter(s => s.enrollmentStatus === 1).length
  const notStartedCount = students.filter(s => s.enrollmentStatus === 0).length

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {/* Status Distribution */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Student Status</h3>
        <div className="h-64">
          <Doughnut data={statusData} options={statusOptions} />
        </div>
      </div>

      {/* Progress Distribution */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Progress Distribution</h3>
        <div className="h-64">
          <Bar data={progressData} options={progressOptions} />
        </div>
      </div>

      {/* Quick Stats */}
      <div className="bg-white rounded-xl shadow-md p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Course Status</h3>
        <div className="space-y-4">
          {/* Completed */}
          <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="font-medium text-gray-900">Completed</span>
            </div>
            <span className="text-2xl font-bold text-green-600">{completedCount}</span>
          </div>

          {/* In Progress */}
          <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <span className="font-medium text-gray-900">In Progress</span>
            </div>
            <span className="text-2xl font-bold text-blue-600">{inProgressCount}</span>
          </div>

          {/* Not Started */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gray-200 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <span className="font-medium text-gray-900">Not Started</span>
            </div>
            <span className="text-2xl font-bold text-gray-600">{notStartedCount}</span>
          </div>

          {/* Average Progress */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-500">Average Progress</span>
              <span className="font-bold text-gray-900">{summary.averageProgress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="h-3 rounded-full transition-all duration-500"
                style={{
                  width: `${summary.averageProgress}%`,
                  backgroundColor: summary.averageProgress >= 75 ? '#22c55e' : summary.averageProgress >= 40 ? '#3b82f6' : '#f97316'
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Charts
