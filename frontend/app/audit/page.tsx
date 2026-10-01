'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'
import type { AuditEvent } from '@/types'
import { FileSearch } from 'lucide-react'

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAuditEvents()
  }, [])

  const loadAuditEvents = async () => {
    try {
      setLoading(true)
      const data = await api.getAuditEvents()
      setEvents(data)
    } catch (err) {
      console.error('Failed to load audit events:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Audit Trail</h1>
        <p className="text-gray-600 mt-1">Complete chronological record of all system actions</p>
      </div>

      {events.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <FileSearch size={48} className="mx-auto mb-4 text-gray-400" />
          <p className="text-gray-600">No audit events recorded yet</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entity</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actor</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Result</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {events.map((event) => (
                  <tr key={event.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatDateTime(event.timestamp)}
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {event.action.replace(/_/g, ' ')}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {event.entity_type} #{event.entity_id}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {event.actor_type}
                      {event.actor_id && ` #${event.actor_id}`}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <ResultBadge result={event.result} />
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 max-w-xs">
                      {event.metadata && Object.keys(event.metadata).length > 0 ? (
                        <details className="cursor-pointer">
                          <summary className="text-blue-600 hover:underline">View metadata</summary>
                          <pre className="mt-2 text-xs bg-gray-50 p-2 rounded overflow-auto">
                            {JSON.stringify(event.metadata, null, 2)}
                          </pre>
                        </details>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function ResultBadge({ result }: { result?: string }) {
  if (!result) return <span className="text-gray-400">-</span>

  const colors: Record<string, string> = {
    SUCCESS: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
    PASS: 'bg-green-100 text-green-800',
    FAIL: 'bg-red-100 text-red-800',
    APPROVED: 'bg-green-100 text-green-800',
    REJECTED: 'bg-red-100 text-red-800',
    PENDING: 'bg-yellow-100 text-yellow-800',
  }

  const color = colors[result] || 'bg-blue-100 text-blue-800'

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${color}`}>
      {result}
    </span>
  )
}
