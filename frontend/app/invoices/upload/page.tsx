'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { Upload, CheckCircle, XCircle, Loader } from 'lucide-react'

export default function UploadInvoicePage() {
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
      setResult(null)
    }
  }

  const handleUpload = async () => {
    if (!file) return

    try {
      setUploading(true)
      setError(null)
      const data = await api.uploadInvoice(file)
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Upload Invoice</h1>
        <p className="text-gray-600 mt-1">Upload invoice documents for automated processing</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            {!file ? (
              <label className="cursor-pointer">
                <Upload size={48} className="mx-auto mb-4 text-gray-400" />
                <p className="text-gray-600 mb-2">Click to select or drag and drop invoice file</p>
                <p className="text-sm text-gray-500">Supported formats: PDF, PNG, JPG (max 10MB)</p>
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileChange}
                />
              </label>
            ) : (
              <div>
                <CheckCircle size={48} className="mx-auto mb-4 text-green-600" />
                <p className="text-gray-900 font-medium">{file.name}</p>
                <p className="text-sm text-gray-500 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                <button
                  onClick={() => setFile(null)}
                  className="text-sm text-blue-600 hover:underline mt-2"
                >
                  Choose different file
                </button>
              </div>
            )}
          </div>

          {file && !result && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="w-full bg-blue-600 text-white px-4 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  Processing...
                </>
              ) : (
                <>
                  <Upload size={20} />
                  Upload and Process
                </>
              )}
            </button>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <XCircle className="text-red-600 flex-shrink-0" size={20} />
              <div>
                <p className="font-medium text-red-900">Upload Failed</p>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
                <CheckCircle className="text-green-600 flex-shrink-0" size={20} />
                <div className="flex-1">
                  <p className="font-medium text-green-900">Invoice Processed Successfully</p>
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Invoice Number:</span>
                      <span className="font-medium">{result.invoice_number}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Vendor:</span>
                      <span className="font-medium">{result.vendor}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Amount:</span>
                      <span className="font-medium">${Number(result.total_amount || 0).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className="font-medium">{result.status}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Decision:</span>
                      <span className={`font-medium ${
                        result.control_result?.decision === 'APPROVED' ? 'text-green-600' :
                        result.control_result?.decision === 'EXCEPTION' ? 'text-red-600' :
                        'text-yellow-600'
                      }`}>
                        {result.control_result?.decision || 'PENDING'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => router.push(`/invoices/${result.invoice_id}`)}
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
                >
                  View Invoice Details
                </button>
                <button
                  onClick={() => {
                    setFile(null)
                    setResult(null)
                  }}
                  className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300"
                >
                  Upload Another
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-medium text-blue-900 mb-2">How it works</h3>
        <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
          <li>Upload your invoice document (PDF, PNG, or JPG)</li>
          <li>NOVA AI automatically extracts invoice data</li>
          <li>System runs control checks (vendor, PO, receipt, duplicate, financial)</li>
          <li>Invoice is routed for approval or exception handling</li>
          <li>Approved invoices automatically create payable obligations</li>
        </ol>
      </div>
    </div>
  )
}
