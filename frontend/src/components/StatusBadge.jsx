import React from 'react'

function StatusBadge({ status }) {
  const getBadgeClass = () => {
    switch (status.class) {
      case 'blue':
        return 'badge-complete'
      case 'green':
        return 'badge-active'
      case 'orange':
        return 'badge-warning'
      case 'red':
        return 'badge-reengage'
      default:
        return 'badge-reengage'
    }
  }

  return (
    <span className={`badge ${getBadgeClass()}`}>
      <span className="mr-1">{status.emoji}</span>
      {status.status}
    </span>
  )
}

export default StatusBadge
