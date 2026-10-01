export interface Invoice {
  id: number;
  invoice_number: string;
  vendor: {
    id: number;
    name: string;
    code?: string;
  };
  purchase_order?: {
    id: number;
    po_number: string;
  };
  total_amount: number;
  currency: string;
  invoice_date: string;
  due_date?: string;
  status: string;
  created_at: string;
}

export interface InvoiceDetail extends Invoice {
  subtotal: number;
  tax_amount: number;
  payment_terms?: string;
  extraction_confidence?: number;
  items: InvoiceItem[];
  control_results: ControlResult[];
  exceptions: Exception[];
  approvals: Approval[];
  updated_at: string;
}

export interface InvoiceItem {
  id: number;
  description: string;
  sku?: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  line_total: number;
}

export interface ControlResult {
  id: number;
  control_name: string;
  status: 'PASS' | 'WARNING' | 'FAIL' | 'REVIEW';
  severity: string;
  message: string;
  details: any;
  created_at: string;
}

export interface Exception {
  id: number;
  invoice_id: number;
  invoice_number?: string;
  vendor_name?: string;
  type: string;
  severity: string;
  status: string;
  message: string;
  resolution?: string;
  created_at: string;
  resolved_at?: string;
}

export interface Approval {
  id: number;
  invoice_id: number;
  invoice_number?: string;
  vendor_name?: string;
  amount?: number;
  level: string;
  status: string;
  comment?: string;
  approved_at?: string;
  created_at: string;
}

export interface PayableObligation {
  id: number;
  invoice_id: number;
  invoice_number?: string;
  vendor: {
    id: number;
    name: string;
    code: string;
    email?: string;
  };
  amount: number;
  currency: string;
  invoice_date: string;
  due_date?: string;
  payment_status: string;
  payment_reference?: string;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  actor_type: string;
  actor_id?: number;
  result?: string;
  metadata?: any;
  timestamp: string;
}

export interface DashboardData {
  summary: {
    total_invoices: number;
    pending_review: number;
    approved: number;
    exceptions: number;
    payable_amount: number;
    overdue_amount: number;
    paid_amount: number;
  };
  recent_invoices: Invoice[];
  exception_breakdown: { type: string; count: number }[];
  status_distribution: { status: string; count: number }[];
  recent_activity: AuditEvent[];
}
