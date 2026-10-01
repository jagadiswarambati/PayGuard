'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import type { Approval } from '@/types'
import { CheckSquare, CheckCircle, XCircle, Search, RefreshCw, Eye } from 'lucide-react'

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('PENDING')
  const [search, setSearch] = useState('')

  // Action state
  const [activeModal, setActiveModal] = useState<'approve' | 'reject' | null>(null)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadApprovals()
  }, [filter])

  const loadApprovals = async () => {
    try {
      setLoading(true)
      const data = await api.getApprovals(filter === 'ALL' ? undefined : filter)
      setApprovals(data)
    } catch (err) {
      console.error('Failed to load approvals:', err)
    } finally {
      setLoading(false)
    }
  }

  const openAction = (approval: Approval, type: 'approve' | 'reject') => {
    setSelectedApproval(approval)
    setActiveModal(type)
    setComment('')
  }

  const handleActionSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedApproval || !activeModal) return

    try {
      setSubmitting(true)
      if (activeModal === 'approve') {
        await api.approveInvoice(selectedApproval.id, comment, 'Finance Approver')
      } else {
        await api.rejectApproval(selectedApproval.id, comment, 'Finance Approver')
      }
      setActiveModal(null)
      setSelectedApproval(null)
      await loadApprovals()
    } catch (err: any) {
      alert(err.message || 'Action failed')
    } finally {
      setSubmitting(false)
    }
  }

  const filteredApprovals = approvals.filter((app) => {
    if (!search.trim()) return true
    const term = search.toLowerCase()
    return (
      (app.invoice_number && app.invoice_number.toLowerCase().includes(term)) ||
      (app.vendor_name && app.vendor_name.toLowerCase().includes(term)) ||
      app.level.toLowerCase().includes(term)
    )
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <CheckSquare className="text-blue-600" /> Approval Routing
          </h1>
          <p className="text-gray-600 mt-1">
            Enforce multi-tier approval authority policies before obligations can be scheduled for payment
          </p>
        </div>
        <button
          onClick={loadApprovals}
          className="flex items-center gap-2 border px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex gap-2">
          <FilterButton active={filter === 'PENDING'} onClick={() => setFilter('PENDING')}>Pending Approval</FilterButton>
          <FilterButton active={filter === 'APPROVED'} onClick={() => setFilter('APPROVED')}>Approved</FilterButton>
          <FilterButton active={filter === 'REJECTED'} onClick={() => setFilter('REJECTED')}>Rejected</FilterButton>
          <FilterButton active={filter === 'ALL'} onClick={() => setFilter('ALL')}>All</FilterButton>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search approvals..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 border rounded-lg w-full text-sm outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      ) : filteredApprovals.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
          <CheckSquare size={48} className="mx-auto mb-4 opacity-40" />
          <h3 className="text-lg font-medium text-gray-900">No {filter !== 'ALL' ? filter.toLowerCase() : ''} approvals found</h3>
          <p className="text-sm text-gray-500 mt-1">Invoices satisfying controls will route here according to authority limits.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase">
                <tr>
                  <th className="px-6 py-3 text-left">Invoice</th>
                  <th className="px-6 py-3 text-left">Vendor</th>
                  <th className="px-6 py-3 text-left">Invoice Amount</th>
                  <th className="px-6 py-3 text-left">Required Level</th>
                  <th className="px-6 py-3 text-left">Status</th>
                  <th className="px-6 py-3 text-left">Routing Date</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200 text-sm">
                {filteredApprovals.map((approval) => (
                  <tr key={approval.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <Link href={`/invoices/${approval.invoice_id}`} className="font-semibold text-blue-600 hover:underline">
                        {approval.invoice_number || `Invoice #${approval.invoice_id}`}
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-gray-900 font-medium">
                      {approval.vendor_name || 'Unknown'}
                    </td>
                    <td className="px-6 py-4 font-bold text-gray-900">
                      {approval.amount ? formatCurrency(approval.amount, approval.currency || 'USD') : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <LevelBadge level={approval.level} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={approval.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-500">
                      {formatDateTime(approval.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right space-x-2">
                      {approval.status === 'PENDING' ? (
                        <>
                          <button
                            onClick={() => openAction(approval, 'approve')}
                            className="bg-green-600 text-white px-3 py-1 rounded text-xs font-medium hover:bg-green-700 transition"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => openAction(approval, 'reject')}
                            className="bg-red-600 text-white px-3 py-1 rounded text-xs font-medium hover:bg-red-700 transition"
                          >
                            Reject
                          </button>
                        </>
                      ) : (
                        <Link
                          href={`/invoices/${approval.invoice_id}`}
                          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                        >
                          <Eye size={14} /> View Invoice
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* APPROVAL DECISION MODAL */}
      {activeModal && selectedApproval && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 border-b pb-3">
              {activeModal === 'approve' ? (
                <CheckCircle className="text-green-600" size={24} />
              ) : (
                <XCircle className="text-red-600" size={24} />
              )}
              <div>
                <h3 className="font-bold text-gray-900 text-lg capitalize">{activeModal} Invoice Payment</h3>
                <p className="text-xs text-gray-500">
                  {selectedApproval.invoice_number} • {selectedApproval.vendor_name}
                </p>
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-600">Total Amount:</span>
                <span className="font-bold text-gray-900">
                  {formatCurrency(selectedApproval.amount || 0, selectedApproval.currency || 'USD')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Authority Tier:</span>
                <span className="font-semibold">{selectedApproval.level} Level Approval</span>
              </div>
            </div>

            <form onSubmit={handleActionSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {activeModal === 'reject' ? (
                    <span className="text-red-600 font-semibold">* Rejection Reason (Mandatory):</span>
                  ) : (
                    'Approval Notes / Comments (Optional):'
                  )}
                </label>
                <textarea
                  required={activeModal === 'reject'}
                  rows={3}
                  placeholder={
                    activeModal === 'reject'
                      ? 'Specify why this payment approval is denied...'
                      : 'Add any approval verification notes...'
                  }
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {activeModal === 'approve' && (
                <p className="text-xs text-green-700 bg-green-50 p-2 rounded">
                  Upon satisfaction of the required approval chain, a formal payable obligation will automatically be generated in the Payable Ledger.
                </p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setActiveModal(null)
                    setSelectedApproval(null)
                  }}
                  className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className={`px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 ${
                    activeModal === 'reject'
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-green-600 hover:bg-green-700'
                  }`}
                >
                  {submitting ? 'Processing...' : `Confirm ${activeModal.toUpperCase()}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
        active ? 'bg-blue-600 text-white shadow-sm' : 'bg-white text-gray-700 hover:bg-gray-50 border'
      }`}
    >
      {children}
    </button>
  )
}

function LevelBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    LOW: 'bg-blue-100 text-blue-800',
    MEDIUM: 'bg-indigo-100 text-indigo-800',
    HIGH: 'bg-purple-100 text-purple-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[level] || 'bg-gray-100 text-gray-800'}`}>
      {level} Tier
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    PENDING: 'bg-yellow-100 text-yellow-800',
    APPROVED: 'bg-green-100 text-green-800',
    REJECTED: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  )
}
