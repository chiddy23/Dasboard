import React from 'react'

function ProgressBar({ progress, showLabel = true }) {
  const getProgressClass = () => {
    switch (progress.colorClass) {
      case 'high':
        return 'progress-high'
      case 'med':
        return 'progress-med'
      case 'low':
        return 'progress-low'
      default:
        return 'progress-low'
    }
  }

  return (
    <div className="flex items-center space-x-2">
      <div className="flex-1 progress-bar">
        <div
          className={`progress-fill ${getProgressClass()}`}
          style={{ width: `${progress.value}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-sm font-medium text-gray-700 w-12 text-right">
          {progress.display}
        </span>
      )}
    </div>
  )
}

export default ProgressBar
