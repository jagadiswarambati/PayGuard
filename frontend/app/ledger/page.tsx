'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { formatCurrency, formatDate } from '@/lib/utils'
import type { PayableObligation } from '@/types'
import { DollarSign, CheckCircle2, Calendar, PauseCircle, Search, RefreshCw, Eye, CreditCard } from 'lucide-react'

export default function LedgerPage() {
  const [obligations, setObligations] = useState<PayableObligation[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('UNPAID')
  const [search, setSearch] = useState('')

  // Action State
  const [paymentModalOpen, setPaymentModalOpen] = useState(false)
  const [selectedObligation, setSelectedObligation] = useState<PayableObligation | null>(null)
  const [paymentReference, setPaymentReference] = useState('')
  const [paymentNote, setPaymentNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadObligations()
  }, [filter])

  const loadObligations = async () => {
    try {
      setLoading(true)
      const data = await api.getPayableObligations(filter === 'ALL' ? undefined : filter)
      setObligations(data)
    } catch (err) {
      console.error('Failed to load payable obligations:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenPay = (obl: PayableObligation) => {
    setSelectedObligation(obl)
    setPaymentReference(`PMT-${Math.floor(100000 + Math.random() * 900000)}`)
    setPaymentNote('')
    setPaymentModalOpen(true)
  }

  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedObligation) return

    try {
      setSubmitting(true)
      await api.recordPayment(selectedObligation.id, paymentReference, paymentNote)
      setPaymentModalOpen(false)
      setSelectedObligation(null)
      await loadObligations()
    } catch (err: any) {
      alert(err.message || 'Payment execution failed')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      await api.updatePaymentStatus(id, newStatus)
      await loadObligations()
    } catch (err: any) {
      alert(err.message || 'Status update failed')
    }
  }

  const totalAmount = obligations.reduce((sum, obl) => sum + (obl.amount || 0), 0)

  const filteredObligations = obligations.filter((obl) => {
    if (!search.trim()) return true
    const term = search.toLowerCase()
    return (
      (obl.invoice_number && obl.invoice_number.toLowerCase().includes(term)) ||
      (obl.vendor?.name && obl.vendor.name.toLowerCase().includes(term)) ||
      (obl.payment_reference && obl.payment_reference.toLowerCase().includes(term))
    )
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <DollarSign className="text-green-600" /> Accounts Payable Ledger
          </h1>
          <p className="text-gray-600 mt-1">
            Valid obligations created automatically only after passing mandatory controls and required approvals
          </p>
        </div>
        <button
          onClick={loadObligations}
          className="flex items-center gap-2 border px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Summary Card */}
      <div className="bg-white rounded-lg shadow p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-green-50 text-green-700 rounded-xl">
            <DollarSign size={32} />
          </div>
          <div>
            <div className="text-xs uppercase font-bold text-gray-500 tracking-wider">
              Total {filter !== 'ALL' ? filter : 'All'} Obligations
            </div>
            <div className="text-3xl font-bold text-gray-900 mt-0.5">
              {formatCurrency(totalAmount)}
            </div>
          </div>
        </div>
        <div className="text-xs text-gray-500 bg-gray-50 p-2.5 rounded-lg border">
          ✓ Verified against approved purchase orders and receipts
        </div>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex flex-wrap gap-2">
          <FilterButton active={filter === 'UNPAID'} onClick={() => setFilter('UNPAID')}>Unpaid</FilterButton>
          <FilterButton active={filter === 'SCHEDULED'} onClick={() => setFilter('SCHEDULED')}>Scheduled</FilterButton>
          <FilterButton active={filter === 'PAID'} onClick={() => setFilter('PAID')}>Paid</FilterButton>
          <FilterButton active={filter === 'ON_HOLD'} onClick={() => setFilter('ON_HOLD')}>On Hold</FilterButton>
          <FilterButton active={filter === 'ALL'} onClick={() => setFilter('ALL')}>All</FilterButton>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
          <input
            type="text"
            placeholder="Search by invoice, vendor, or ref..."
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
      ) : filteredObligations.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
          <DollarSign size={48} className="mx-auto mb-4 opacity-40" />
          <h3 className="text-lg font-medium text-gray-900">No {filter !== 'ALL' ? filter.toLowerCase() : ''} obligations found</h3>
          <p className="text-sm text-gray-500 mt-1">Invoices appear here automatically once controls and approvals are completed.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase">
                <tr>
                  <th className="px-6 py-3 text-left">Invoice #</th>
                  <th className="px-6 py-3 text-left">Vendor</th>
                  <th className="px-6 py-3 text-left">Payable Amount</th>
                  <th className="px-6 py-3 text-left">Invoice Date</th>
                  <th className="px-6 py-3 text-left">Due Date</th>
                  <th className="px-6 py-3 text-left">Payment Status</th>
                  <th className="px-6 py-3 text-left">Reference</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200 text-sm">
                {filteredObligations.map((obl) => (
                  <tr key={obl.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <Link href={`/invoices/${obl.invoice_id}`} className="font-semibold text-blue-600 hover:underline">
                        {obl.invoice_number || `Invoice #${obl.invoice_id}`}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900">{obl.vendor?.name || 'Unknown'}</div>
                      <div className="text-xs text-gray-500">{obl.vendor?.code || ''}</div>
                    </td>
                    <td className="px-6 py-4 font-bold text-gray-900">
                      {formatCurrency(obl.amount, obl.currency || 'USD')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                      {formatDate(obl.invoice_date)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                      {obl.due_date ? formatDate(obl.due_date) : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={obl.payment_status} />
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-gray-600">
                      {obl.payment_reference || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right space-x-1 text-xs">
                      {obl.payment_status === 'UNPAID' && (
                        <>
                          <button
                            onClick={() => handleOpenPay(obl)}
                            className="bg-green-600 text-white px-2.5 py-1 rounded font-medium hover:bg-green-700 transition"
                          >
                            Pay
                          </button>
                          <button
                            onClick={() => handleStatusChange(obl.id, 'SCHEDULED')}
                            className="bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded font-medium hover:bg-blue-100 transition"
                          >
                            Schedule
                          </button>
                          <button
                            onClick={() => handleStatusChange(obl.id, 'ON_HOLD')}
                            className="bg-gray-100 text-gray-700 px-2.5 py-1 rounded font-medium hover:bg-gray-200 transition"
                          >
                            Hold
                          </button>
                        </>
                      )}
                      {obl.payment_status === 'SCHEDULED' && (
                        <>
                          <button
                            onClick={() => handleOpenPay(obl)}
                            className="bg-green-600 text-white px-2.5 py-1 rounded font-medium hover:bg-green-700 transition"
                          >
                            Execute Payment
                          </button>
                          <button
                            onClick={() => handleStatusChange(obl.id, 'UNPAID')}
                            className="text-gray-600 hover:underline px-2 py-1"
                          >
                            Unschedule
                          </button>
                        </>
                      )}
                      {obl.payment_status === 'ON_HOLD' && (
                        <button
                          onClick={() => handleStatusChange(obl.id, 'UNPAID')}
                          className="bg-blue-600 text-white px-2.5 py-1 rounded font-medium hover:bg-blue-700 transition"
                        >
                          Release Hold
                        </button>
                      )}
                      {obl.payment_status === 'PAID' && (
                        <span className="text-green-700 text-xs font-semibold px-2 py-1">
                          ✓ Settled
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RECORD PAYMENT MODAL */}
      {paymentModalOpen && selectedObligation && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 border-b pb-3">
              <CreditCard className="text-green-600" size={24} />
              <div>
                <h3 className="font-bold text-gray-900 text-lg">Execute Payment</h3>
                <p className="text-xs text-gray-500">
                  {selectedObligation.invoice_number} • {selectedObligation.vendor?.name}
                </p>
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-600">Payable Amount:</span>
                <span className="font-bold text-gray-900 text-base">
                  {formatCurrency(selectedObligation.amount, selectedObligation.currency || 'USD')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Vendor Payment Terms:</span>
                <span className="font-semibold">{selectedObligation.vendor?.payment_terms || 'Net 30'}</span>
              </div>
            </div>

            <form onSubmit={handleRecordPayment} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Payment Reference / Trace Number (Check #, Wire ID, ACH Trace):
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. ACH-9812401 or CHK-4412"
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Optional Settlement Note:
                </label>
                <input
                  type="text"
                  placeholder="e.g. Disbursed via Corporate Treasury Account"
                  value={paymentNote}
                  onChange={(e) => setPaymentNote(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setPaymentModalOpen(false)
                    setSelectedObligation(null)
                  }}
                  className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  {submitting ? 'Recording...' : 'Confirm Payment'}
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

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    UNPAID: 'bg-yellow-100 text-yellow-800',
    SCHEDULED: 'bg-blue-100 text-blue-800',
    PAID: 'bg-green-100 text-green-800',
    ON_HOLD: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  )
}
