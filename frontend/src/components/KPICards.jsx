import React from 'react'

function KPICards({ summary }) {
  const cards = [
    {
      title: 'Active',
      value: summary.activeCount,
      subtitle: 'Last 24 hours',
      emoji: '🟢',
      bgColor: 'bg-green-50',
      iconBg: 'bg-green-100',
      textColor: 'text-green-800',
      borderColor: 'border-l-4 border-green-500'
    },
    {
      title: 'Warning',
      value: summary.warningCount,
      subtitle: '24-72 hours ago',
      emoji: '🟡',
      bgColor: 'bg-orange-50',
      iconBg: 'bg-orange-100',
      textColor: 'text-orange-800',
      borderColor: 'border-l-4 border-orange-500'
    },
    {
      title: 'Re-engage',
      value: summary.reengageCount,
      subtitle: '72+ hours ago',
      emoji: '🔴',
      bgColor: 'bg-red-50',
      iconBg: 'bg-red-100',
      textColor: 'text-red-800',
      borderColor: 'border-l-4 border-red-500'
    },
    {
      title: 'Total Students',
      value: summary.totalStudents,
      subtitle: 'In department',
      emoji: '👥',
      bgColor: 'bg-blue-50',
      iconBg: 'bg-blue-100',
      textColor: 'text-blue-800',
      borderColor: 'border-l-4 border-blue-500'
    },
    {
      title: 'Avg Progress',
      value: `${summary.averageProgress}%`,
      subtitle: 'Course completion',
      emoji: '📊',
      bgColor: 'bg-purple-50',
      iconBg: 'bg-purple-100',
      textColor: 'text-purple-800',
      borderColor: 'border-l-4 border-purple-500'
    }
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`kpi-card ${card.bgColor} ${card.borderColor} animate-fadeIn`}
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <div className="flex items-start justify-between">
            <div>
              <p className={`text-sm font-medium ${card.textColor} mb-1`}>{card.title}</p>
              <p className="text-3xl font-bold text-gray-900">{card.value}</p>
              <p className="text-xs text-gray-500 mt-1">{card.subtitle}</p>
            </div>
            <div className={`kpi-icon ${card.iconBg} text-2xl`}>
              {card.emoji}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default KPICards
