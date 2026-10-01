'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { api } from '@/lib/api'
import { formatCurrency, formatDate, formatDateTime } from '@/lib/utils'
import type { InvoiceDetail } from '@/types'
import {
  CheckCircle, XCircle, AlertCircle, AlertTriangle, Play, RefreshCw,
  Clock, DollarSign, FileText, ArrowLeft, ShieldAlert, CheckCircle2
} from 'lucide-react'

export default function InvoiceDetailPage() {
  const params = useParams()
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [reprocessing, setReprocessing] = useState(false)

  // Action modals
  const [actionType, setActionType] = useState<'resolve_exc' | 'override_exc' | 'approve' | 'reject' | null>(null)
  const [actionTargetId, setActionTargetId] = useState<number | null>(null)
  const [actionInput, setActionInput] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (params.id) {
      loadInvoice()
    }
  }, [params.id])

  const loadInvoice = async () => {
    try {
      setLoading(true)
      const data = await api.getInvoice(params.id as string)
      setInvoice(data)
    } catch (err) {
      console.error('Failed to load invoice:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRerunControls = async () => {
    if (!invoice) return
    try {
      setReprocessing(true)
      await api.processInvoice(invoice.id)
      await loadInvoice()
    } catch (err: any) {
      alert(err.message || 'Processing failed')
    } finally {
      setReprocessing(false)
    }
  }

  const handleActionSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!actionTargetId || !actionType) return

    try {
      setSubmitting(true)
      if (actionType === 'resolve_exc') {
        await api.resolveException(actionTargetId, actionInput)
      } else if (actionType === 'override_exc') {
        await api.overrideException(actionTargetId, actionInput, 'AP Supervisor')
      } else if (actionType === 'approve') {
        await api.approveInvoice(actionTargetId, actionInput)
      } else if (actionType === 'reject') {
        await api.rejectApproval(actionTargetId, actionInput)
      }
      setActionType(null)
      setActionTargetId(null)
      await loadInvoice()
    } catch (err: any) {
      alert(err.message || 'Action failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!invoice) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Invoice not found</p>
        <Link href="/invoices" className="text-blue-600 hover:underline mt-2 inline-block">
          Return to Invoices
        </Link>
      </div>
    )
  }

  const openExceptions = invoice.exceptions?.filter(e => e.status === 'OPEN' || e.status === 'IN_REVIEW') || []
  const pendingApprovals = invoice.approvals?.filter(a => a.status === 'PENDING') || []

  return (
    <div className="space-y-6 max-w-6xl pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <Link href="/invoices" className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 mb-2">
            <ArrowLeft size={14} /> Back to Invoices
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-gray-900">{invoice.invoice_number}</h1>
            <StatusBadge status={invoice.status} />
          </div>
          <p className="text-gray-500 text-sm mt-0.5">
            Processed via FIN-06 AP Control System • Ingested on {formatDateTime(invoice.created_at)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRerunControls}
            disabled={reprocessing}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
          >
            <Play size={16} /> {reprocessing ? 'Evaluating Controls...' : 'Re-Run Controls'}
          </button>
          <button
            onClick={loadInvoice}
            className="p-2 border rounded-lg hover:bg-gray-50 transition text-gray-600"
            title="Refresh"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* Action Alerts if Pending */}
      {openExceptions.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
          <ShieldAlert className="text-amber-600 flex-shrink-0 mt-0.5" size={20} />
          <div className="flex-1">
            <h4 className="font-semibold text-amber-900 text-sm">
              Action Required: {openExceptions.length} Open Control Discrepanc{openExceptions.length > 1 ? 'ies' : 'y'}
            </h4>
            <p className="text-xs text-amber-800 mt-1">
              This invoice cannot become a payable obligation until all control exceptions are reviewed and either resolved or overridden with business justification.
            </p>
          </div>
        </div>
      )}

      {/* Summary Grid */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 border-b pb-2">Invoice Summary & Verification</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">Vendor Master</div>
            <div className="font-semibold text-gray-900 mt-1">{invoice.vendor?.name || 'Unknown'}</div>
            <div className="text-xs text-gray-500 mt-0.5">
              Code: {invoice.vendor?.code || 'Unregistered'} • Status: {invoice.vendor?.status || 'UNVERIFIED'}
            </div>
          </div>

          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">Purchase Order</div>
            <div className="font-semibold text-gray-900 mt-1">
              {invoice.purchase_order ? invoice.purchase_order.po_number : 'None Reference Provided'}
            </div>
            {invoice.purchase_order && (
              <div className="text-xs text-gray-500 mt-0.5">
                PO Amount: {formatCurrency(invoice.purchase_order.total_amount || 0)} ({invoice.purchase_order.status})
              </div>
            )}
          </div>

          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">Invoice Dates</div>
            <div className="text-sm font-semibold text-gray-900 mt-1">Date: {formatDate(invoice.invoice_date)}</div>
            <div className="text-xs text-gray-500 mt-0.5">
              Due: {invoice.due_date ? formatDate(invoice.due_date) : 'Net 30'}
            </div>
          </div>

          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">Payable Total</div>
            <div className="text-2xl font-bold text-gray-900 mt-0.5">
              {formatCurrency(invoice.total_amount, invoice.currency)}
            </div>
            <div className="text-xs text-gray-500">
              Subtotal: {formatCurrency(invoice.subtotal)} + Tax: {formatCurrency(invoice.tax_amount)}
            </div>
          </div>
        </div>

        {invoice.extraction_confidence !== undefined && (
          <div className="mt-4 pt-3 border-t text-xs text-gray-500 flex items-center justify-between">
            <span>Extraction Confidence: <strong>{(invoice.extraction_confidence * 100).toFixed(0)}%</strong></span>
            <span>Terms: <strong>{invoice.payment_terms || 'Net 30'}</strong></span>
          </div>
        )}
      </div>

      {/* Line Items Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-4 border-b bg-gray-50">
          <h2 className="text-sm font-semibold text-gray-900">Extracted Line Items ({invoice.items?.length || 0})</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-6 py-2.5 text-left">Description</th>
                <th className="px-6 py-2.5 text-left">SKU</th>
                <th className="px-6 py-2.5 text-right">Quantity</th>
                <th className="px-6 py-2.5 text-right">Unit Price</th>
                <th className="px-6 py-2.5 text-right">Tax Rate</th>
                <th className="px-6 py-2.5 text-right">Line Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {invoice.items && invoice.items.length > 0 ? (
                invoice.items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3 font-medium text-gray-900">{item.description}</td>
                    <td className="px-6 py-3 font-mono text-xs text-gray-500">{item.sku || '-'}</td>
                    <td className="px-6 py-3 text-right">{item.quantity}</td>
                    <td className="px-6 py-3 text-right">{formatCurrency(item.unit_price, invoice.currency)}</td>
                    <td className="px-6 py-3 text-right">{(item.tax_rate * 100).toFixed(1)}%</td>
                    <td className="px-6 py-3 text-right font-semibold">{formatCurrency(item.line_total, invoice.currency)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-4 text-center text-gray-500 text-xs">
                    No individual line items parsed
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Control Engine Results */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <div className="flex justify-between items-center border-b pb-3">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Deterministic Control Engine Checks</h2>
            <p className="text-xs text-gray-500">Every check is independently evaluated from persistent database records</p>
          </div>
        </div>

        <div className="space-y-3">
          {invoice.control_results && invoice.control_results.length > 0 ? (
            invoice.control_results.map((control) => (
              <div
                key={control.id}
                className={`flex items-start gap-3 p-3.5 rounded-lg border transition-all ${
                  control.status === 'PASS'
                    ? 'bg-green-50/50 border-green-200'
                    : control.status === 'WARNING'
                    ? 'bg-amber-50/50 border-amber-200'
                    : 'bg-red-50/50 border-red-200'
                }`}
              >
                {control.status === 'PASS' && <CheckCircle className="text-green-600 flex-shrink-0 mt-0.5" size={20} />}
                {control.status === 'WARNING' && <AlertTriangle className="text-amber-600 flex-shrink-0 mt-0.5" size={20} />}
                {control.status === 'FAIL' && <XCircle className="text-red-600 flex-shrink-0 mt-0.5" size={20} />}
                {control.status === 'REVIEW' && <AlertCircle className="text-blue-600 flex-shrink-0 mt-0.5" size={20} />}

                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900 text-sm">
                      {control.control_name.replace(/_/g, ' ')}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold ${
                        control.status === 'PASS'
                          ? 'bg-green-100 text-green-800'
                          : control.status === 'WARNING'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {control.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-700 mt-1">{control.message}</p>
                </div>
              </div>
            ))
          ) : (
            <p className="text-xs text-gray-500 italic">No control evaluation records available.</p>
          )}
        </div>
      </div>

      {/* Exceptions Section with Interactive Resolve & Override */}
      {invoice.exceptions && invoice.exceptions.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <h2 className="text-base font-semibold text-gray-900 border-b pb-2">
            Discrepancy Exceptions ({invoice.exceptions.length})
          </h2>

          <div className="space-y-3">
            {invoice.exceptions.map((exc) => (
              <div key={exc.id} className="p-4 border rounded-lg space-y-2 bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-gray-900 text-sm">
                    {exc.type.replace(/_/g, ' ')}
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      exc.status === 'OPEN'
                        ? 'bg-red-100 text-red-800'
                        : exc.status === 'RESOLVED'
                        ? 'bg-green-100 text-green-800'
                        : exc.status === 'OVERRIDDEN'
                        ? 'bg-purple-100 text-purple-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {exc.status}
                  </span>
                </div>
                <p className="text-xs text-gray-700">{exc.message}</p>

                {exc.override_reason && (
                  <div className="text-xs bg-purple-50 text-purple-900 p-2 rounded border border-purple-200">
                    <strong>Override Justification:</strong> {exc.override_reason}
                  </div>
                )}
                {exc.resolution && !exc.override_reason && (
                  <div className="text-xs bg-green-50 text-green-900 p-2 rounded border border-green-200">
                    <strong>Resolution Action:</strong> {exc.resolution}
                  </div>
                )}

                {(exc.status === 'OPEN' || exc.status === 'IN_REVIEW') && (
                  <div className="flex gap-2 pt-2 border-t">
                    <button
                      onClick={() => {
                        setActionTargetId(exc.id)
                        setActionType('resolve_exc')
                        setActionInput('')
                      }}
                      className="bg-green-600 text-white text-xs px-3 py-1 rounded hover:bg-green-700 font-medium"
                    >
                      Resolve Exception
                    </button>
                    <button
                      onClick={() => {
                        setActionTargetId(exc.id)
                        setActionType('override_exc')
                        setActionInput('')
                      }}
                      className="bg-amber-600 text-white text-xs px-3 py-1 rounded hover:bg-amber-700 font-medium"
                    >
                      Override with Justification
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Approvals Workflow Chain */}
      {invoice.approvals && invoice.approvals.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <h2 className="text-base font-semibold text-gray-900 border-b pb-2">
            Approval Routing Chain
          </h2>

          <div className="space-y-3">
            {invoice.approvals.map((approval) => (
              <div key={approval.id} className="p-3.5 border rounded-lg flex items-center justify-between">
                <div>
                  <div className="font-semibold text-sm text-gray-900">
                    {approval.level} Tier Approval
                  </div>
                  {approval.comment && (
                    <div className="text-xs text-gray-600 mt-0.5">Comment: {approval.comment}</div>
                  )}
                  {approval.approved_at && (
                    <div className="text-xs text-gray-500 mt-0.5">Approved on {formatDateTime(approval.approved_at)}</div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-1 rounded text-xs font-bold ${
                      approval.status === 'APPROVED'
                        ? 'bg-green-100 text-green-800'
                        : approval.status === 'REJECTED'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {approval.status}
                  </span>

                  {approval.status === 'PENDING' && (
                    <div className="flex gap-1.5 ml-2">
                      <button
                        onClick={() => {
                          setActionTargetId(approval.id)
                          setActionType('approve')
                          setActionInput('')
                        }}
                        className="bg-green-600 text-white text-xs px-3 py-1 rounded hover:bg-green-700 font-medium"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => {
                          setActionTargetId(approval.id)
                          setActionType('reject')
                          setActionInput('')
                        }}
                        className="bg-red-600 text-white text-xs px-3 py-1 rounded hover:bg-red-700 font-medium"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Payable Obligation Card */}
      {invoice.payable_obligation && (
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-600 space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <CheckCircle2 className="text-green-600" size={20} /> Generated Payable Obligation
            </h2>
            <Link
              href="/ledger"
              className="text-xs text-blue-600 hover:underline font-medium"
            >
              View in Ledger →
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-gray-500">Payable Amount:</span>
              <div className="font-bold text-base text-gray-900 mt-0.5">
                {formatCurrency(invoice.payable_obligation.amount, invoice.payable_obligation.currency)}
              </div>
            </div>
            <div>
              <span className="text-gray-500">Payment Status:</span>
              <div className="mt-0.5">
                <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded font-semibold text-xs">
                  {invoice.payable_obligation.payment_status}
                </span>
              </div>
            </div>
            <div>
              <span className="text-gray-500">Settlement Reference:</span>
              <div className="font-mono mt-0.5">{invoice.payable_obligation.payment_reference || 'Unsettled'}</div>
            </div>
            <div>
              <span className="text-gray-500">Created:</span>
              <div className="mt-0.5">{formatDate(invoice.payable_obligation.created_at)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Audit Trail Timeline */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-base font-semibold text-gray-900 border-b pb-2 flex items-center gap-2">
          <Clock size={18} className="text-blue-600" /> Full Audit Trail History
        </h2>

        {invoice.audit_events && invoice.audit_events.length > 0 ? (
          <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
            {invoice.audit_events.map((event) => (
              <div key={event.id} className="relative text-xs">
                <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-blue-600 ring-4 ring-white" />
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-semibold text-gray-900">{event.action.replace(/_/g, ' ')}</span>
                    <span className="text-gray-500 ml-2">by {event.actor_type}</span>
                  </div>
                  <span className="text-gray-400">{formatDateTime(event.timestamp)}</span>
                </div>
                {event.metadata && Object.keys(event.metadata).length > 0 && (
                  <pre className="mt-1 bg-gray-50 p-2 rounded text-[11px] font-mono text-gray-600 overflow-x-auto">
                    {JSON.stringify(event.metadata, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-500 italic">No audit records logged yet.</p>
        )}
      </div>

      {/* ACTION DIALOG MODAL */}
      {actionType && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-gray-900 text-base capitalize">
              {actionType === 'resolve_exc' && 'Resolve Control Exception'}
              {actionType === 'override_exc' && 'Override Control Exception (Mandatory Reason)'}
              {actionType === 'approve' && 'Approve Invoice Payment'}
              {actionType === 'reject' && 'Reject Invoice Approval'}
            </h3>

            <form onSubmit={handleActionSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  {actionType === 'override_exc' && '* Business Override Justification:'}
                  {actionType === 'reject' && '* Rejection Reason:'}
                  {actionType === 'resolve_exc' && 'Resolution Notes:'}
                  {actionType === 'approve' && 'Approval Notes (Optional):'}
                </label>
                <textarea
                  required={actionType === 'override_exc' || actionType === 'reject'}
                  rows={3}
                  value={actionInput}
                  onChange={(e) => setActionInput(e.target.value)}
                  className="w-full border rounded-lg p-2.5 text-xs outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter notes..."
                />
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActionType(null)}
                  className="px-3 py-1.5 border rounded-lg text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? 'Submitting...' : 'Confirm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
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
    <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
