'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { formatDateTime, formatCurrency } from '@/lib/utils'
import type { Exception } from '@/types'
import { AlertCircle, CheckCircle2, ShieldAlert, UserCheck, XCircle, Search, RefreshCw, Eye } from 'lucide-react'

export default function ExceptionsPage() {
  const [exceptions, setExceptions] = useState<Exception[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('OPEN')
  const [search, setSearch] = useState('')

  // Action Modals State
  const [activeModal, setActiveModal] = useState<'resolve' | 'override' | 'reassign' | 'reject' | null>(null)
  const [selectedException, setSelectedException] = useState<Exception | null>(null)
  const [formInput, setFormInput] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadExceptions()
  }, [filter])

  const loadExceptions = async () => {
    try {
      setLoading(true)
      const data = await api.getExceptions(filter === 'ALL' ? undefined : filter)
      setExceptions(data)
    } catch (err) {
      console.error('Failed to load exceptions:', err)
    } finally {
      setLoading(false)
    }
  }

  const openAction = (exc: Exception, type: 'resolve' | 'override' | 'reassign' | 'reject') => {
    setSelectedException(exc)
    setActiveModal(type)
    setFormInput('')
  }

  const handleActionSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedException || !activeModal) return

    try {
      setSubmitting(true)
      if (activeModal === 'resolve') {
        await api.resolveException(selectedException.id, formInput)
      } else if (activeModal === 'override') {
        await api.overrideException(selectedException.id, formInput, 'AP Supervisor')
      } else if (activeModal === 'reassign') {
        await api.reassignException(selectedException.id, formInput)
      } else if (activeModal === 'reject') {
        await api.rejectException(selectedException.id, formInput)
      }
      setActiveModal(null)
      setSelectedException(null)
      await loadExceptions()
    } catch (err: any) {
      alert(err.message || 'Operation failed')
    } finally {
      setSubmitting(false)
    }
  }

  const filteredExceptions = exceptions.filter((exc) => {
    if (!search.trim()) return true
    const term = search.toLowerCase()
    return (
      exc.type.toLowerCase().includes(term) ||
      (exc.invoice_number && exc.invoice_number.toLowerCase().includes(term)) ||
      (exc.vendor_name && exc.vendor_name.toLowerCase().includes(term)) ||
      exc.message.toLowerCase().includes(term)
    )
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <AlertCircle className="text-red-600" /> Control Exceptions
          </h1>
          <p className="text-gray-600 mt-1">
            Investigate, resolve, override, or reassign invoices flagged by the AP Control Engine
          </p>
        </div>
        <button
          onClick={loadExceptions}
          className="flex items-center gap-2 border px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex flex-wrap gap-2">
          <FilterButton active={filter === 'OPEN'} onClick={() => setFilter('OPEN')}>Open</FilterButton>
          <FilterButton active={filter === 'IN_REVIEW'} onClick={() => setFilter('IN_REVIEW')}>In Review</FilterButton>
          <FilterButton active={filter === 'RESOLVED'} onClick={() => setFilter('RESOLVED')}>Resolved</FilterButton>
          <FilterButton active={filter === 'OVERRIDDEN'} onClick={() => setFilter('OVERRIDDEN')}>Overridden</FilterButton>
          <FilterButton active={filter === 'REJECTED'} onClick={() => setFilter('REJECTED')}>Rejected</FilterButton>
          <FilterButton active={filter === 'ALL'} onClick={() => setFilter('ALL')}>All</FilterButton>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search exceptions or invoices..."
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
      ) : filteredExceptions.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <AlertCircle size={48} className="mx-auto mb-4 text-gray-300" />
          <h3 className="text-lg font-medium text-gray-900">No {filter !== 'ALL' ? filter.toLowerCase() : ''} exceptions</h3>
          <p className="text-gray-500 text-sm mt-1">
            {search ? 'No results matched your search term.' : 'All control validations passed without any open discrepancies.'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase">
                <tr>
                  <th className="px-6 py-3 text-left">Discrepancy Type</th>
                  <th className="px-6 py-3 text-left">Invoice / Vendor</th>
                  <th className="px-6 py-3 text-left">Control Failure Message</th>
                  <th className="px-6 py-3 text-left">Severity</th>
                  <th className="px-6 py-3 text-left">Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200 text-sm">
                {filteredExceptions.map((exc) => (
                  <tr key={exc.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-gray-900">{exc.type.replace(/_/g, ' ')}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{formatDateTime(exc.created_at)}</div>
                    </td>
                    <td className="px-6 py-4">
                      <Link href={`/invoices/${exc.invoice_id}`} className="font-medium text-blue-600 hover:underline">
                        {exc.invoice_number || `Invoice #${exc.invoice_id}`}
                      </Link>
                      <div className="text-gray-600 text-xs mt-0.5">
                        {exc.vendor_name || 'Unknown'} {exc.amount ? `• ${formatCurrency(exc.amount, exc.currency || 'USD')}` : ''}
                      </div>
                    </td>
                    <td className="px-6 py-4 max-w-md">
                      <div className="text-gray-800 text-xs leading-relaxed">{exc.message}</div>
                      {exc.override_reason && (
                        <div className="mt-1 text-xs text-amber-700 bg-amber-50 p-1.5 rounded border border-amber-200">
                          <strong>Override Justification:</strong> {exc.override_reason}
                        </div>
                      )}
                      {exc.resolution && !exc.override_reason && (
                        <div className="mt-1 text-xs text-green-700 bg-green-50 p-1.5 rounded border border-green-200">
                          <strong>Resolution:</strong> {exc.resolution}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <SeverityBadge severity={exc.severity} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={exc.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-xs space-x-1">
                      {exc.status === 'OPEN' || exc.status === 'IN_REVIEW' ? (
                        <>
                          <button
                            onClick={() => openAction(exc, 'resolve')}
                            className="bg-green-50 text-green-700 hover:bg-green-100 border border-green-200 px-2.5 py-1 rounded font-medium transition"
                          >
                            Resolve
                          </button>
                          <button
                            onClick={() => openAction(exc, 'override')}
                            className="bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 px-2.5 py-1 rounded font-medium transition"
                          >
                            Override
                          </button>
                          <button
                            onClick={() => openAction(exc, 'reassign')}
                            className="bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 px-2.5 py-1 rounded font-medium transition"
                          >
                            Assign
                          </button>
                          <button
                            onClick={() => openAction(exc, 'reject')}
                            className="bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 px-2.5 py-1 rounded font-medium transition"
                          >
                            Reject
                          </button>
                        </>
                      ) : (
                        <Link
                          href={`/invoices/${exc.invoice_id}`}
                          className="inline-flex items-center gap-1 text-blue-600 hover:underline px-2 py-1"
                        >
                          <Eye size={14} /> View
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

      {/* ACTION MODAL */}
      {activeModal && selectedException && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center gap-3 border-b pb-3">
              {activeModal === 'resolve' && <CheckCircle2 className="text-green-600" size={24} />}
              {activeModal === 'override' && <ShieldAlert className="text-amber-600" size={24} />}
              {activeModal === 'reassign' && <UserCheck className="text-blue-600" size={24} />}
              {activeModal === 'reject' && <XCircle className="text-red-600" size={24} />}
              <div>
                <h3 className="font-bold text-gray-900 text-lg capitalize">{activeModal} Exception</h3>
                <p className="text-xs text-gray-500">
                  {selectedException.invoice_number} • {selectedException.type.replace(/_/g, ' ')}
                </p>
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-700 font-mono">
              <strong>Control Failure:</strong> {selectedException.message}
            </div>

            <form onSubmit={handleActionSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-800 mb-1">
                  {activeModal === 'override' && (
                    <span className="text-red-600 font-semibold">* Mandatory Business Override Justification:</span>
                  )}
                  {activeModal === 'resolve' && 'Resolution Explanation:'}
                  {activeModal === 'reassign' && 'Assign To (Reviewer Name or Department):'}
                  {activeModal === 'reject' && 'Reason for Rejection:'}
                </label>
                <textarea
                  required
                  rows={activeModal === 'reassign' ? 2 : 4}
                  placeholder={
                    activeModal === 'override'
                      ? 'Explain why this control failure is acceptable (e.g. Authorized by CFO due to pre-negotiated volume discount amendment)'
                      : activeModal === 'resolve'
                      ? 'Detail the resolution action taken (e.g. Corrected line item SKU and matched with receipt)'
                      : activeModal === 'reassign'
                      ? 'e.g. John Doe (Procurement Manager)'
                      : 'Detail why this invoice is rejected'
                  }
                  value={formInput}
                  onChange={(e) => setFormInput(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {activeModal === 'override' && (
                <p className="text-xs text-amber-700 bg-amber-50 p-2 rounded">
                  <strong>Notice:</strong> This override will be logged in the permanent audit trail. It does not erase the control failure, ensuring full audit traceability.
                </p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setActiveModal(null)
                    setSelectedException(null)
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
                      : activeModal === 'override'
                      ? 'bg-amber-600 hover:bg-amber-700'
                      : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {submitting ? 'Submitting...' : `Confirm ${activeModal.toUpperCase()}`}
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

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    LOW: 'bg-blue-100 text-blue-800',
    MEDIUM: 'bg-yellow-100 text-yellow-800',
    HIGH: 'bg-orange-100 text-orange-800',
    CRITICAL: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[severity] || 'bg-gray-100 text-gray-800'}`}>
      {severity}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    OPEN: 'bg-red-100 text-red-800',
    IN_REVIEW: 'bg-yellow-100 text-yellow-800',
    RESOLVED: 'bg-green-100 text-green-800',
    OVERRIDDEN: 'bg-purple-100 text-purple-800',
    REJECTED: 'bg-gray-100 text-gray-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  )
}
