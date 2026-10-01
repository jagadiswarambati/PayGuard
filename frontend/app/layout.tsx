import './globals.css'
import type { Metadata } from 'next'
import Link from 'next/link'
import { Home, FileText, AlertCircle, CheckSquare, DollarSign, FileSearch, Settings as SettingsIcon } from 'lucide-react'

export const metadata: Metadata = {
  title: 'FIN-06 AP Control System',
  description: 'Accounts Payable Control Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex">
          {/* Sidebar */}
          <aside className="w-64 bg-gray-900 text-white p-6">
            <div className="mb-8">
              <h1 className="text-xl font-bold">FIN-06</h1>
              <p className="text-gray-400 text-sm">AP Control System</p>
            </div>
            
            <nav className="space-y-2">
              <NavLink href="/" icon={<Home size={20} />}>Dashboard</NavLink>
              <NavLink href="/invoices" icon={<FileText size={20} />}>Invoices</NavLink>
              <NavLink href="/exceptions" icon={<AlertCircle size={20} />}>Exceptions</NavLink>
              <NavLink href="/approvals" icon={<CheckSquare size={20} />}>Approvals</NavLink>
              <NavLink href="/ledger" icon={<DollarSign size={20} />}>Payable Ledger</NavLink>
              <NavLink href="/audit" icon={<FileSearch size={20} />}>Audit Trail</NavLink>
              <NavLink href="/settings" icon={<SettingsIcon size={20} />}>Settings</NavLink>
            </nav>
          </aside>

          
          {/* Main content */}
          <main className="flex-1 p-8 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}

function NavLink({ href, icon, children }: { href: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-4 py-2 rounded-lg hover:bg-gray-800 transition-colors"
    >
      {icon}
      <span>{children}</span>
    </Link>
  )
}
