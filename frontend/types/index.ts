export interface Vendor {
  id: number;
  vendor_code: string;
  name: string;
  tax_id?: string;
  email?: string;
  status: 'ACTIVE' | 'INACTIVE' | 'BLOCKED';
  payment_terms?: string;
}

export interface PurchaseOrderItem {
  id: number;
  description: string;
  sku?: string;
  quantity: number;
  unit_price: number;
  tax_rate?: number;
  line_total: number;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  vendor_id: number;
  vendor_name?: string;
  po_date?: string;
  currency: string;
  status: 'OPEN' | 'PARTIALLY_RECEIVED' | 'RECEIVED' | 'CLOSED' | 'CANCELLED';
  total_amount: number;
  items?: PurchaseOrderItem[];
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
  amount?: number;
  currency?: string;
  type: string;
  severity: string;
  status: 'OPEN' | 'IN_REVIEW' | 'RESOLVED' | 'REJECTED' | 'OVERRIDDEN';
  message: string;
  resolution?: string;
  resolution_notes?: string;
  override_reason?: string;
  assigned_to_name?: string;
  created_at: string;
  resolved_at?: string;
}

export interface Approval {
  id: number;
  invoice_id: number;
  invoice_number?: string;
  vendor_name?: string;
  amount?: number;
  currency?: string;
  level: 'LOW' | 'MEDIUM' | 'HIGH';
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  comment?: string;
  approved_at?: string;
  created_at: string;
}

export interface PayableObligation {
  id: number;
  invoice_id: number;
  invoice_number?: string;
  vendor?: {
    id: number;
    name: string;
    code: string;
    email?: string;
    payment_terms?: string;
  };
  amount: number;
  currency: string;
  invoice_date: string;
  due_date?: string;
  approval_status?: string;
  payment_status: 'UNPAID' | 'SCHEDULED' | 'PAID' | 'ON_HOLD';
  payment_reference?: string;
  created_at: string;
  updated_at?: string;
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

export interface Invoice {
  id: number;
  invoice_number: string;
  vendor?: {
    id?: number;
    name: string;
    code?: string;
    status?: string;
    tax_id?: string;
  };
  vendor_name?: string;
  purchase_order?: {
    id: number;
    po_number: string;
    total_amount?: number;
    status?: string;
  };
  total_amount: number;
  amount?: number;
  currency: string;
  invoice_date: string;
  due_date?: string;
  status: 'RECEIVED' | 'PROCESSING' | 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' | 'ON_HOLD' | 'PAID';
  extraction_confidence?: number;
  created_at: string;
}


export interface InvoiceDetail extends Invoice {
  subtotal: number;
  tax_amount: number;
  payment_terms?: string;
  items: InvoiceItem[];
  control_results: ControlResult[];
  exceptions: Exception[];
  approvals: Approval[];
  payable_obligation?: PayableObligation | null;
  audit_events?: AuditEvent[];
  updated_at: string;
}

export interface SystemSettings {
  po_price_tolerance: number;
  po_quantity_tolerance: number;
  approval_threshold_low: number;
  approval_threshold_medium: number;
  auto_approval_enabled: boolean;
  currency_default: string;
}

export interface DashboardData {
  summary: {
    total_invoices: number;
    pending_review: number;
    approved: number;
    rejected?: number;
    on_hold?: number;
    exceptions: number;
    total_exceptions?: number;
    pending_approvals: number;
    payable_amount: number;
    overdue_amount: number;
    paid_amount: number;
  };
  recent_invoices: Invoice[];
  exception_breakdown: { type: string; count: number }[];
  status_distribution: { status: string; count: number }[];
  recent_activity: AuditEvent[];
}
