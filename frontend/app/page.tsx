'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import type { DashboardData } from '@/types'
import {
  Upload, TrendingUp, AlertTriangle, CheckCircle2, DollarSign,
  FileText, AlertCircle, Clock, CheckSquare, RefreshCw, ArrowRight
} from 'lucide-react'
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
    } catch (err: any) {
      setError('Unable to connect to AP Control API. Please ensure the backend server is running.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 text-sm">Querying real-time accounts payable metrics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-800 space-y-3">
        <div className="flex items-center gap-3">
          <AlertCircle className="text-red-600" size={24} />
          <h2 className="text-lg font-bold">API Connection Error</h2>
        </div>
        <p className="text-sm">{error}</p>
        <button
          onClick={loadDashboard}
          className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition"
        >
          Retry Connection
        </button>
      </div>
    )
  }

  if (!data) {
    return <div className="text-center py-12 text-gray-500">No dashboard metrics available.</div>
  }

  const { summary, recent_invoices, exception_breakdown, status_distribution, recent_activity } = data
  const isEmptyState = summary.total_invoices === 0

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Accounts Payable Control Hub</h1>
          <p className="text-gray-600 mt-1 text-sm">
            Evidence-based AP controls: Validating vendors, purchase orders, goods receipts, and duplicate protection
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/invoices/upload"
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 font-medium transition text-sm shadow-sm"
          >
            <Upload size={16} /> Upload Invoice
          </Link>
          <button
            onClick={loadDashboard}
            className="p-2.5 border rounded-lg hover:bg-gray-50 transition text-gray-600"
            title="Refresh Data"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* EMPTY DATABASE STATE */}
      {isEmptyState ? (
        <div className="bg-white rounded-xl shadow p-12 text-center space-y-4 max-w-2xl mx-auto my-8 border">
          <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto">
            <FileText size={32} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Database Ready • Zero Hardcoded Data</h2>
          <p className="text-gray-600 text-sm leading-relaxed">
            The AP control system is initialized with persistent relational database tables. All metrics are calculated dynamically from actual records.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row justify-center gap-3">
            <Link
              href="/invoices/upload"
              className="bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700 shadow-sm"
            >
              Upload First Invoice
            </Link>
            <Link
              href="/settings"
              className="border border-gray-300 text-gray-700 px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-gray-50"
            >
              Configure Master Data & Tolerances
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* Key AP Counters */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Total Ingested"
              value={summary.total_invoices}
              icon={<FileText className="text-blue-600" size={22} />}
              subtitle="All invoices tracked"
            />
            <MetricCard
              title="Pending Review"
              value={summary.pending_review}
              icon={<AlertTriangle className="text-amber-600" size={22} />}
              subtitle="Action required"
              alert={summary.pending_review > 0}
            />
            <MetricCard
              title="Open Exceptions"
              value={summary.exceptions}
              icon={<AlertCircle className="text-red-600" size={22} />}
              subtitle="Discrepancies flagged"
              alert={summary.exceptions > 0}
            />
            <MetricCard
              title="Pending Approvals"
              value={summary.pending_approvals || 0}
              icon={<CheckSquare className="text-indigo-600" size={22} />}
              subtitle="Awaiting authority sign-off"
              alert={(summary.pending_approvals || 0) > 0}
            />
          </div>

          {/* Financial Amounts Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl shadow p-5 border-l-4 border-blue-600">
              <div className="flex items-center justify-between text-gray-500 text-xs font-semibold uppercase tracking-wider">
                <span>Total Payable Obligation</span>
                <DollarSign className="text-blue-600" size={18} />
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-2">
                {formatCurrency(summary.payable_amount)}
              </div>
              <div className="text-xs text-gray-500 mt-1">Authorized obligations in Payable Ledger</div>
            </div>

            <div className="bg-white rounded-xl shadow p-5 border-l-4 border-red-500">
              <div className="flex items-center justify-between text-gray-500 text-xs font-semibold uppercase tracking-wider">
                <span>Overdue Obligations</span>
                <AlertTriangle className="text-red-600" size={18} />
              </div>
              <div className="text-2xl font-bold text-red-600 mt-2">
                {formatCurrency(summary.overdue_amount)}
              </div>
              <div className="text-xs text-gray-500 mt-1">Past stipulated payment due date</div>
            </div>

            <div className="bg-white rounded-xl shadow p-5 border-l-4 border-green-500">
              <div className="flex items-center justify-between text-gray-500 text-xs font-semibold uppercase tracking-wider">
                <span>Disbursed & Paid</span>
                <TrendingUp className="text-green-600" size={18} />
              </div>
              <div className="text-2xl font-bold text-green-700 mt-2">
                {formatCurrency(summary.paid_amount)}
              </div>
              <div className="text-xs text-gray-500 mt-1">Settled payments with trace reference</div>
            </div>
          </div>

          {/* Recent Invoices & Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Invoices */}
            <div className="bg-white rounded-xl shadow overflow-hidden">
              <div className="p-4 border-b flex justify-between items-center bg-gray-50/50">
                <h2 className="font-semibold text-gray-900 text-sm">Recent Invoices</h2>
                <Link href="/invoices" className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                  View All <ArrowRight size={12} />
                </Link>
              </div>
              <div className="divide-y divide-gray-100">
                {recent_invoices.slice(0, 6).map((inv) => (
                  <Link
                    key={inv.id}
                    href={`/invoices/${inv.id}`}
                    className="p-3.5 flex items-center justify-between hover:bg-gray-50 transition block"
                  >
                    <div>
                      <div className="font-semibold text-sm text-gray-900">{inv.invoice_number}</div>
                      <div className="text-xs text-gray-500">{inv.vendor_name || 'Unknown'}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-sm text-gray-900">{formatCurrency(inv.amount ?? inv.total_amount ?? 0, inv.currency)}</div>
                      <StatusBadge status={inv.status} />
                    </div>
                  </Link>
                ))}
              </div>
            </div>

            {/* Recent Audit Trail Events */}
            <div className="bg-white rounded-xl shadow overflow-hidden">
              <div className="p-4 border-b flex justify-between items-center bg-gray-50/50">
                <h2 className="font-semibold text-gray-900 text-sm">System Audit Trail Stream</h2>
                <Link href="/audit" className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                  Full Log <ArrowRight size={12} />
                </Link>
              </div>
              <div className="divide-y divide-gray-100 p-2">
                {recent_activity.slice(0, 6).map((act) => (
                  <div key={act.id} className="p-2 text-xs flex justify-between items-start">
                    <div>
                      <span className="font-semibold text-gray-800">{act.action.replace(/_/g, ' ')}</span>
                      <div className="text-gray-500 text-[11px] mt-0.5">
                        {act.entity_type} #{act.entity_id} • {act.result || 'OK'}
                      </div>
                    </div>
                    <span className="text-gray-400 text-[11px]">{formatDateTime(act.timestamp)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Exception Category Breakdown */}
          {exception_breakdown && exception_breakdown.length > 0 && (
            <div className="bg-white rounded-xl shadow p-5 space-y-3">
              <div className="flex justify-between items-center border-b pb-2">
                <h3 className="font-semibold text-sm text-gray-900">Open Control Discrepancies by Category</h3>
                <Link href="/exceptions" className="text-xs text-blue-600 hover:underline">
                  Manage Exceptions →
                </Link>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                {exception_breakdown.map((exc) => (
                  <div key={exc.type} className="p-3 bg-red-50/60 border border-red-200 rounded-lg">
                    <div className="text-xl font-bold text-red-700">{exc.count}</div>
                    <div className="text-xs text-gray-700 mt-1 font-medium">{exc.type.replace(/_/g, ' ')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function MetricCard({
  title,
  value,
  icon,
  subtitle,
  alert,
}: {
  title: string
  value: number
  icon: React.ReactNode
  subtitle: string
  alert?: boolean
}) {
  return (
    <div className={`bg-white rounded-xl shadow p-5 ${alert ? 'ring-2 ring-amber-400' : ''}`}>
      <div className="flex items-center justify-between text-gray-500 text-xs font-semibold uppercase tracking-wider mb-2">
        <span>{title}</span>
        {icon}
      </div>
      <div className="text-3xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    RECEIVED: 'bg-blue-100 text-blue-800',
    PROCESSING: 'bg-yellow-100 text-yellow-800',
    PENDING_REVIEW: 'bg-orange-100 text-orange-800',
    APPROVED: 'bg-green-100 text-green-800',
    REJECTED: 'bg-red-100 text-red-800',
    ON_HOLD: 'bg-purple-100 text-purple-800',
    PAID: 'bg-emerald-100 text-emerald-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
