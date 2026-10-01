'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import type { DashboardData } from '@/types'
import { Upload, TrendingUp, AlertTriangle, CheckCircle, DollarSign } from 'lucide-react'
import Link from 'next/link'

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadDashboard()
  }, [])

  const loadDashboard = async () => {
    try {
      setLoading(true)
      const dashboardData = await api.getDashboard()
      setData(dashboardData)
      setError(null)
    } catch (err) {
      setError('Failed to load dashboard')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading dashboard...</p>
      </div>
    </div>
  }

  if (error) {
    return <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
      {error}
    </div>
  }

  if (!data) {
    return <div className="text-center text-gray-600">No data available</div>
  }

  const { summary, recent_invoices, exception_breakdown, status_distribution, recent_activity } = data

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AP Control Dashboard</h1>
          <p className="text-gray-600 mt-1">Real-time accounts payable monitoring and control</p>
        </div>
        <Link
          href="/invoices/upload"
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Upload size={20} />
          Upload Invoice
        </Link>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Invoices"
          value={summary.total_invoices}
          icon={<FileText className="text-blue-600" size={24} />}
          subtitle="All time"
        />
        <MetricCard
          title="Pending Review"
          value={summary.pending_review}
          icon={<AlertTriangle className="text-yellow-600" size={24} />}
          subtitle="Requires attention"
          alert={summary.pending_review > 0}
        />
        <MetricCard
          title="Exceptions"
          value={summary.exceptions}
          icon={<AlertCircle className="text-red-600" size={24} />}
          subtitle="Open issues"
          alert={summary.exceptions > 0}
        />
        <MetricCard
          title="Approved"
          value={summary.approved}
          icon={<CheckCircle className="text-green-600" size={24} />}
          subtitle="Ready for payment"
        />
      </div>

      {/* Financial Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600">Payable Amount</span>
            <DollarSign className="text-blue-600" size={20} />
          </div>
          <div className="text-2xl font-bold text-gray-900">
            {formatCurrency(summary.payable_amount)}
          </div>
          <div className="text-sm text-gray-500 mt-1">Unpaid obligations</div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600">Overdue Amount</span>
            <AlertTriangle className="text-red-600" size={20} />
          </div>
          <div className="text-2xl font-bold text-red-600">
            {formatCurrency(summary.overdue_amount)}
          </div>
          <div className="text-sm text-gray-500 mt-1">Past due date</div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600">Paid Amount</span>
            <TrendingUp className="text-green-600" size={20} />
          </div>
          <div className="text-2xl font-bold text-green-600">
            {formatCurrency(summary.paid_amount)}
          </div>
          <div className="text-sm text-gray-500 mt-1">Completed payments</div>
        </div>
      </div>

      {/* Recent Invoices and Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-lg font-semibold">Recent Invoices</h2>
          </div>
          <div className="p-6">
            {recent_invoices.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileText size={48} className="mx-auto mb-2 opacity-50" />
                <p>No invoices received yet</p>
                <Link href="/invoices/upload" className="text-blue-600 hover:underline mt-2 inline-block">
                  Upload your first invoice
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {recent_invoices.slice(0, 5).map((invoice) => (
                  <Link
                    key={invoice.id}
                    href={`/invoices/${invoice.id}`}
                    className="block p-3 hover:bg-gray-50 rounded-lg transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="font-medium">{invoice.invoice_number}</div>
                        <div className="text-sm text-gray-600">{invoice.vendor?.name || 'Unknown'}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold">{formatCurrency(invoice.total_amount)}</div>
                        <StatusBadge status={invoice.status} />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b">
            <h2 className="text-lg font-semibold">Recent Activity</h2>
          </div>
          <div className="p-6">
            {recent_activity.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileSearch size={48} className="mx-auto mb-2 opacity-50" />
                <p>No activity yet</p>
              </div>
            ) : (
              <div className="space-y-3">
                {recent_activity.slice(0, 8).map((event) => (
                  <div key={event.id} className="text-sm">
                    <div className="flex justify-between items-start">
                      <span className="font-medium text-gray-700">{event.action.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-gray-500">{formatDateTime(event.timestamp)}</span>
                    </div>
                    <div className="text-gray-600 text-xs mt-1">
                      {event.entity_type} #{event.entity_id}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Exception Breakdown */}
      {exception_breakdown.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Open Exceptions by Type</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {exception_breakdown.map((exc) => (
              <div key={exc.type} className="border rounded-lg p-4">
                <div className="text-2xl font-bold text-red-600">{exc.count}</div>
                <div className="text-sm text-gray-600 mt-1">{exc.type.replace(/_/g, ' ')}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({ title, value, icon, subtitle, alert }: {
  title: string
  value: number
  icon: React.ReactNode
  subtitle: string
  alert?: boolean
}) {
  return (
    <div className={`bg-white rounded-lg shadow p-6 ${alert ? 'ring-2 ring-yellow-400' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-600">{title}</span>
        {icon}
      </div>
      <div className="text-3xl font-bold text-gray-900">{value}</div>
      <div className="text-sm text-gray-500 mt-1">{subtitle}</div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors = {
    RECEIVED: 'bg-blue-100 text-blue-800',
    PROCESSING: 'bg-yellow-100 text-yellow-800',
    PENDING_REVIEW: 'bg-orange-100 text-orange-800',
    APPROVED: 'bg-green-100 text-green-800',
    REJECTED: 'bg-red-100 text-red-800',
    ON_HOLD: 'bg-gray-100 text-gray-800',
    PAID: 'bg-green-100 text-green-800',
  }

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status as keyof typeof colors] || 'bg-gray-100 text-gray-800'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function FileText({ size, className }: { size?: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size || 24}
      height={size || 24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  )
}

function FileSearch({ size, className }: { size?: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size || 24}
      height={size || 24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <circle cx="11.5" cy="14.5" r="2.5" />
      <path d="M13.25 16.25L15 18" />
    </svg>
  )
}

function AlertCircle({ size, className }: { size?: number; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size || 24}
      height={size || 24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}
