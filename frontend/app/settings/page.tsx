'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import type { SystemSettings, Vendor, PurchaseOrder } from '@/types'
import { Settings as SettingsIcon, Shield, Sliders, CheckCircle, Plus, Users, ShoppingCart, RefreshCw } from 'lucide-react'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'rules' | 'vendors' | 'pos'>('rules')
  const [settings, setSettings] = useState<SystemSettings>({
    po_price_tolerance: 0.05,
    po_quantity_tolerance: 0.05,
    approval_threshold_low: 5000,
    approval_threshold_medium: 25000,
    auto_approval_enabled: true,
    currency_default: 'USD',
  })
  const [vendors, setVendors] = useState<Vendor[]>([])
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Modals for adding vendor / PO
  const [showVendorModal, setShowVendorModal] = useState(false)
  const [showPOModal, setShowPOModal] = useState(false)

  // New Vendor Form
  const [newVendor, setNewVendor] = useState({
    vendor_code: '',
    name: '',
    tax_id: '',
    email: '',
    status: 'ACTIVE',
    payment_terms: 'Net 30'
  })

  // New PO Form
  const [newPO, setNewPO] = useState({
    po_number: '',
    vendor_id: 1,
    currency: 'USD',
    description: '',
    sku: '',
    quantity: 1,
    unit_price: 100
  })

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    try {
      setLoading(true)
      const [s, v, p] = await Promise.all([
        api.getSettings().catch(() => null),
        api.getVendors().catch(() => []),
        api.getPurchaseOrders().catch(() => [])
      ])
      if (s) setSettings(s)
      if (v) setVendors(v)
      if (p) setPos(p)
      if (v && v.length > 0) {
        setNewPO(prev => ({ ...prev, vendor_id: v[0].id }))
      }
    } catch (err: any) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSaving(true)
      setFeedback(null)
      await api.updateSettings({
        po_price_tolerance: Number(settings.po_price_tolerance),
        po_quantity_tolerance: Number(settings.po_quantity_tolerance),
        approval_threshold_low: Number(settings.approval_threshold_low),
        approval_threshold_medium: Number(settings.approval_threshold_medium),
        auto_approval_enabled: Boolean(settings.auto_approval_enabled),
      })
      setFeedback({ type: 'success', message: 'Control parameters and approval thresholds updated successfully!' })
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to update settings' })
    } finally {
      setSaving(false)
    }
  }

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createVendor(newVendor)
      setShowVendorModal(false)
      setNewVendor({ vendor_code: '', name: '', tax_id: '', email: '', status: 'ACTIVE', payment_terms: 'Net 30' })
      loadAll()
      setFeedback({ type: 'success', message: 'Vendor added to master registry' })
    } catch (err: any) {
      alert(err.message || 'Failed to create vendor')
    }
  }

  const handleCreatePO = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createPurchaseOrder({
        po_number: newPO.po_number,
        vendor_id: Number(newPO.vendor_id),
        currency: newPO.currency,
        items: [
          {
            description: newPO.description || 'Standard Goods Item',
            sku: newPO.sku || 'SKU-001',
            quantity: Number(newPO.quantity),
            unit_price: Number(newPO.unit_price)
          }
        ]
      })
      setShowPOModal(false)
      setNewPO(prev => ({ ...prev, po_number: '', description: '', sku: '' }))
      loadAll()
      setFeedback({ type: 'success', message: 'Purchase Order created successfully' })
    } catch (err: any) {
      alert(err.message || 'Failed to create purchase order')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <SettingsIcon className="text-blue-600" /> System Settings & Controls
          </h1>
          <p className="text-gray-600 mt-1">
            Configure financial tolerances, multi-tier approval thresholds, and approved master data
          </p>
        </div>
        <button
          onClick={loadAll}
          className="flex items-center gap-2 border px-3 py-2 rounded-lg text-sm hover:bg-gray-50 transition"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {feedback && (
        <div
          className={`p-4 rounded-lg flex items-center gap-3 ${
            feedback.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          <CheckCircle size={20} />
          <span className="font-medium text-sm">{feedback.message}</span>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-gray-200 gap-4">
        <button
          onClick={() => setActiveTab('rules')}
          className={`pb-3 font-medium text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'rules'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Sliders size={18} /> Control Tolerances & Approvals
        </button>
        <button
          onClick={() => setActiveTab('vendors')}
          className={`pb-3 font-medium text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'vendors'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Users size={18} /> Approved Vendors ({vendors.length})
        </button>
        <button
          onClick={() => setActiveTab('pos')}
          className={`pb-3 font-medium text-sm flex items-center gap-2 border-b-2 transition-colors ${
            activeTab === 'pos'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <ShoppingCart size={18} /> Purchase Orders ({pos.length})
        </button>
      </div>

      {/* TAB 1: RULES & TOLERANCES */}
      {activeTab === 'rules' && (
        <form onSubmit={handleSaveSettings} className="space-y-6">
          {/* Tolerances Card */}
          <div className="bg-white rounded-lg shadow p-6 space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2 border-b pb-3">
              <Shield className="text-blue-600" size={20} /> Purchase Order Matching Tolerances
            </h2>
            <p className="text-sm text-gray-600">
              Deterministic threshold margins applied by the control engine during PO price and quantity matching.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  PO Price Variance Tolerance (±%)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={settings.po_price_tolerance}
                    onChange={(e) =>
                      setSettings({ ...settings, po_price_tolerance: parseFloat(e.target.value) || 0 })
                    }
                    className="border rounded-lg px-3 py-2 w-full focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <span className="text-gray-500 font-semibold text-sm">
                    ({(settings.po_price_tolerance * 100).toFixed(0)}%)
                  </span>
                </div>
                <span className="text-xs text-gray-500">Default: 0.05 (±5% price variance allowed)</span>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  PO Quantity Variance Tolerance (±%)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={settings.po_quantity_tolerance}
                    onChange={(e) =>
                      setSettings({ ...settings, po_quantity_tolerance: parseFloat(e.target.value) || 0 })
                    }
                    className="border rounded-lg px-3 py-2 w-full focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <span className="text-gray-500 font-semibold text-sm">
                    ({(settings.po_quantity_tolerance * 100).toFixed(0)}%)
                  </span>
                </div>
                <span className="text-xs text-gray-500">Default: 0.05 (±5% quantity variance allowed)</span>
              </div>
            </div>
          </div>

          {/* Approval Routing Thresholds */}
          <div className="bg-white rounded-lg shadow p-6 space-y-4">
            <h2 className="text-lg font-semibold flex items-center gap-2 border-b pb-3">
              <Sliders className="text-indigo-600" size={20} /> Multi-Tier Approval Routing Thresholds
            </h2>
            <p className="text-sm text-gray-600">
              Configure financial authority levels and automatic approval qualification limits.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tier 1: Auto-Approval Upper Limit ($/₹)
                </label>
                <input
                  type="number"
                  step="100"
                  min="0"
                  value={settings.approval_threshold_low}
                  onChange={(e) =>
                    setSettings({ ...settings, approval_threshold_low: parseFloat(e.target.value) || 0 })
                  }
                  className="border rounded-lg px-3 py-2 w-full focus:ring-2 focus:ring-blue-500 outline-none"
                />
                <span className="text-xs text-gray-500">
                  Invoices below this amount qualify for automatic approval if all mandatory controls PASS (Default: 5,000).
                </span>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tier 2: Dual Senior Finance Approval Threshold ($/₹)
                </label>
                <input
                  type="number"
                  step="500"
                  min="0"
                  value={settings.approval_threshold_medium}
                  onChange={(e) =>
                    setSettings({ ...settings, approval_threshold_medium: parseFloat(e.target.value) || 0 })
                  }
                  className="border rounded-lg px-3 py-2 w-full focus:ring-2 focus:ring-blue-500 outline-none"
                />
                <span className="text-xs text-gray-500">
                  Invoices equal to or above this amount require Senior Finance dual approval (Default: 25,000).
                </span>
              </div>
            </div>

            <div className="pt-3 border-t flex items-center gap-3">
              <input
                type="checkbox"
                id="autoApproval"
                checked={settings.auto_approval_enabled}
                onChange={(e) => setSettings({ ...settings, auto_approval_enabled: e.target.checked })}
                className="h-4 w-4 text-blue-600 rounded focus:ring-blue-500 cursor-pointer"
              />
              <label htmlFor="autoApproval" className="text-sm text-gray-800 cursor-pointer">
                <strong>Enable Automatic Approval</strong> for invoices below ${settings.approval_threshold_low.toLocaleString()} when all mandatory controls pass without error
              </label>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700 font-medium transition disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Configuration Changes'}
            </button>
          </div>
        </form>
      )}

      {/* TAB 2: VENDORS MASTER */}
      {activeTab === 'vendors' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white p-4 rounded-lg shadow">
            <div>
              <h2 className="font-semibold text-gray-900">Approved Vendor Registry</h2>
              <p className="text-xs text-gray-500">
                Invoices from unregistered or blocked vendors automatically trigger control exceptions.
              </p>
            </div>
            <button
              onClick={() => setShowVendorModal(true)}
              className="flex items-center gap-2 bg-blue-600 text-white px-3 py-2 rounded-lg text-sm hover:bg-blue-700 transition"
            >
              <Plus size={16} /> Add Vendor
            </button>
          </div>

          {vendors.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
              <Users size={48} className="mx-auto mb-2 opacity-50" />
              <p>No vendors registered yet. Add your first vendor to test vendor controls.</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase">
                  <tr>
                    <th className="px-6 py-3 text-left">Code</th>
                    <th className="px-6 py-3 text-left">Name</th>
                    <th className="px-6 py-3 text-left">Tax ID</th>
                    <th className="px-6 py-3 text-left">Terms</th>
                    <th className="px-6 py-3 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 text-sm">
                  {vendors.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-6 py-3 font-mono font-medium">{v.vendor_code}</td>
                      <td className="px-6 py-3 font-semibold text-gray-900">{v.name}</td>
                      <td className="px-6 py-3 text-gray-600">{v.tax_id || '-'}</td>
                      <td className="px-6 py-3 text-gray-600">{v.payment_terms || 'Net 30'}</td>
                      <td className="px-6 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-semibold ${
                            v.status === 'ACTIVE'
                              ? 'bg-green-100 text-green-800'
                              : v.status === 'BLOCKED'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {v.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: PURCHASE ORDERS MASTER */}
      {activeTab === 'pos' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white p-4 rounded-lg shadow">
            <div>
              <h2 className="font-semibold text-gray-900">Purchase Orders Registry</h2>
              <p className="text-xs text-gray-500">
                Validated against incoming invoices for price, quantity, and receipt matching.
              </p>
            </div>
            <button
              onClick={() => setShowPOModal(true)}
              disabled={vendors.length === 0}
              className="flex items-center gap-2 bg-blue-600 text-white px-3 py-2 rounded-lg text-sm hover:bg-blue-700 transition disabled:opacity-50"
            >
              <Plus size={16} /> Create PO
            </button>
          </div>

          {pos.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
              <ShoppingCart size={48} className="mx-auto mb-2 opacity-50" />
              <p>No purchase orders found. Create a purchase order to test 3-way matching.</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase">
                  <tr>
                    <th className="px-6 py-3 text-left">PO #</th>
                    <th className="px-6 py-3 text-left">Vendor</th>
                    <th className="px-6 py-3 text-left">Total</th>
                    <th className="px-6 py-3 text-left">Status</th>
                    <th className="px-6 py-3 text-left">Items</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 text-sm">
                  {pos.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className="px-6 py-3 font-mono font-medium text-blue-600">{p.po_number}</td>
                      <td className="px-6 py-3 text-gray-900">{p.vendor_name || `Vendor #${p.vendor_id}`}</td>
                      <td className="px-6 py-3 font-semibold">{formatCurrency(p.total_amount, p.currency)}</td>
                      <td className="px-6 py-3">
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                          {p.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-xs text-gray-600">
                        {p.items?.map((it) => `${it.quantity}x ${it.description} ($${it.unit_price})`).join(', ') || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* MODAL: ADD VENDOR */}
      {showVendorModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold">Register Approved Vendor</h3>
            <form onSubmit={handleCreateVendor} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700">Vendor Code</label>
                <input
                  required
                  placeholder="e.g. V001"
                  value={newVendor.vendor_code}
                  onChange={(e) => setNewVendor({ ...newVendor, vendor_code: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Vendor Name</label>
                <input
                  required
                  placeholder="e.g. Acme Corporation"
                  value={newVendor.name}
                  onChange={(e) => setNewVendor({ ...newVendor, name: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Tax ID</label>
                <input
                  placeholder="e.g. 12-3456789"
                  value={newVendor.tax_id}
                  onChange={(e) => setNewVendor({ ...newVendor, tax_id: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Status</label>
                <select
                  value={newVendor.status}
                  onChange={(e) => setNewVendor({ ...newVendor, status: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="INACTIVE">INACTIVE</option>
                  <option value="BLOCKED">BLOCKED</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Payment Terms</label>
                <input
                  placeholder="Net 30"
                  value={newVendor.payment_terms}
                  onChange={(e) => setNewVendor({ ...newVendor, payment_terms: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowVendorModal(false)}
                  className="px-4 py-2 border rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 font-medium"
                >
                  Save Vendor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ADD PURCHASE ORDER */}
      {showPOModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold">Create Purchase Order</h3>
            <form onSubmit={handleCreatePO} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700">PO Number</label>
                <input
                  required
                  placeholder="e.g. PO-2024-001"
                  value={newPO.po_number}
                  onChange={(e) => setNewPO({ ...newPO, po_number: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Vendor</label>
                <select
                  value={newPO.vendor_id}
                  onChange={(e) => setNewPO({ ...newPO, vendor_id: Number(e.target.value) })}
                  className="w-full border rounded p-2 text-sm"
                >
                  {vendors.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} ({v.vendor_code})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700">Item Description</label>
                <input
                  required
                  placeholder="e.g. Widget Pro Model A"
                  value={newPO.description}
                  onChange={(e) => setNewPO({ ...newPO, description: e.target.value })}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs font-medium text-gray-700">SKU</label>
                  <input
                    placeholder="WID-A"
                    value={newPO.sku}
                    onChange={(e) => setNewPO({ ...newPO, sku: e.target.value })}
                    className="w-full border rounded p-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700">Quantity</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={newPO.quantity}
                    onChange={(e) => setNewPO({ ...newPO, quantity: parseFloat(e.target.value) || 1 })}
                    className="w-full border rounded p-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    value={newPO.unit_price}
                    onChange={(e) => setNewPO({ ...newPO, unit_price: parseFloat(e.target.value) || 0 })}
                    className="w-full border rounded p-2 text-sm"
                  />
                </div>
              </div>
              <div className="p-2 bg-gray-50 rounded text-xs text-gray-600 flex justify-between">
                <span>Calculated PO Total:</span>
                <span className="font-bold">${(newPO.quantity * newPO.unit_price).toFixed(2)}</span>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPOModal(false)}
                  className="px-4 py-2 border rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 font-medium"
                >
                  Create PO
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
