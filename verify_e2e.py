import os
import json
import httpx
import sys

API_BASE = "http://localhost:8000/api"

def print_step(title):
    print(f"\n{'='*70}\n[STEP] {title}\n{'='*70}")

def run_tests():
    client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)
    
    # 0. Health Check
    print_step("0. Backend Health Check")
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print(f"Health check OK: {res.json()}")

    # 1. Master Data Verification
    print_step("1. Verifying Master Data (Vendors, POs, Receipts)")
    res = client.get("/api/master/vendors")
    assert res.status_code == 200
    vendors = res.json()
    print(f"Loaded {len(vendors)} vendors: {[v['name'] for v in vendors]}")
    acme = next((v for v in vendors if "Acme" in v['name']), None)
    assert acme is not None, "Acme vendor not found in master data"

    res = client.get("/api/master/purchase-orders")
    assert res.status_code == 200
    pos = res.json()
    print(f"Loaded {len(pos)} purchase orders: {[p['po_number'] for p in pos]}")

    # 2. System Settings Verification
    print_step("2. System Settings Verification")
    res = client.get("/api/settings")
    assert res.status_code == 200
    settings = res.json()
    print(f"Current Settings: {json.dumps(settings, indent=2)}")
    assert "po_price_tolerance" in settings

    # 3. Test Case 1: End-to-End Clean Invoice Flow
    print_step("3. Test Case 1: Clean 3-Way Match Invoice (Acme Corp)")
    invoice_1_data = {
        "vendor": {"name": "Acme Corporation", "tax_id": "US-EIN-12-3456789"},
        "invoice_number": "INV-E2E-ACME-001",
        "invoice_date": "2024-03-01",
        "po_number": "PO-2024-001",
        "currency": "USD",
        "payment_terms": "Net 30",
        "subtotal": 5000.00,
        "tax_amount": 400.00,
        "total_amount": 5400.00,
        "line_items": [
            {
                "sku": "SKU-SERVER-01",
                "description": "Enterprise Rack Server Model X",
                "quantity": 2.0,
                "unit_price": 2500.00,
                "tax_rate": 0.08,
                "line_total": 5000.00
            }
        ]
    }
    
    files = {"file": ("inv_acme_001.json", json.dumps(invoice_1_data), "application/json")}
    res = client.post("/api/invoices/upload", files=files)
    assert res.status_code == 200, f"Upload failed: {res.text}"
    inv_1_res = res.json()
    inv_1_id = inv_1_res["id"]
    print(f"Invoice 1 created with ID {inv_1_id}, status: {inv_1_res['status']}")
    print(f"Controls executed: {len(inv_1_res.get('controls', []))}")
    for c in inv_1_res.get("controls", []):
        print(f" - Control {c['control_type']}: {c['status']} ({c.get('details')})")
        assert c['status'] == "PASSED", f"Control {c['control_type']} did not pass: {c}"

    # Verify Detail & Approval Generation
    res = client.get(f"/api/invoices/{inv_1_id}")
    assert res.status_code == 200
    inv_1_detail = res.json()
    print(f"Invoice 1 status: {inv_1_detail['status']}")
    
    # Since total is $5,400 (which is in tier $5,000 - $25,000), it routes to Manager Approval
    approvals = inv_1_detail.get("approvals", [])
    print(f"Generated Approvals: {len(approvals)}")
    assert len(approvals) >= 1, "Expected approval request for $5,400 invoice"
    approval_id = approvals[0]["id"]
    print(f"Pending approval ID: {approval_id}, Role: {approvals[0]['required_role']}")

    # Approve Invoice
    print_step("3b. Approving Invoice 1 (Manager Approval)")
    res = client.post(f"/api/approvals/{approval_id}/approve", json={"notes": "All 3-way match controls passed cleanly. Approved for payment."})
    assert res.status_code == 200, f"Approval failed: {res.text}"
    print("Approval response:", res.json())

    # Verify Invoice Status is APPROVED and Payable Obligation Created
    res = client.get(f"/api/invoices/{inv_1_id}")
    inv_1_updated = res.json()
    assert inv_1_updated["status"] == "APPROVED", f"Expected APPROVED, got {inv_1_updated['status']}"
    assert inv_1_updated.get("payable") is not None, "Payable obligation was not created!"
    payable_id = inv_1_updated["payable"]["id"]
    print(f"Payable Obligation created automatically! Payable ID: {payable_id}, Status: {inv_1_updated['payable']['status']}, Amount: ${inv_1_updated['payable']['amount']}")

    # 4. Test Case 2: Blocked Vendor Detection
    print_step("4. Test Case 2: Blocked Vendor Control Check")
    invoice_2_data = {
        "vendor": {"name": "Blocked Vendor LLC", "tax_id": "US-EIN-99-9999999"},
        "invoice_number": "INV-E2E-BLOCKED-001",
        "invoice_date": "2024-03-02",
        "po_number": "",
        "currency": "USD",
        "subtotal": 1200.00,
        "tax_amount": 0.00,
        "total_amount": 1200.00,
        "line_items": [
            {"description": "Consulting Services", "quantity": 1.0, "unit_price": 1200.00, "line_total": 1200.00}
        ]
    }
    files = {"file": ("inv_blocked.json", json.dumps(invoice_2_data), "application/json")}
    res = client.post("/api/invoices/upload", files=files)
    assert res.status_code == 200
    inv_2_res = res.json()
    print(f"Blocked vendor invoice status: {inv_2_res['status']}")
    assert inv_2_res['status'] in ["REJECTED", "EXCEPTION"], f"Expected REJECTED/EXCEPTION, got {inv_2_res['status']}"
    vendor_ctrl = next((c for c in inv_2_res.get('controls', []) if c['control_type'] == 'VENDOR_VERIFICATION'), None)
    assert vendor_ctrl is not None and vendor_ctrl['status'] == 'FAILED', f"Vendor control did not fail: {vendor_ctrl}"
    print(f"Vendor control correctly failed: {vendor_ctrl['details']}")

    # 5. Test Case 3: 3-Way Match Receipt Mismatch & Exception Override
    print_step("5. Test Case 3: Receipt Quantity Mismatch & Mandatory Override")
    # PO-2024-002 has 50 units ordered, GR-2024-002 has only 30 units received. Invoice claims 50 units.
    invoice_3_data = {
        "vendor": {"name": "Global Supplies Inc", "tax_id": "US-EIN-98-7654321"},
        "invoice_number": "INV-E2E-MISMATCH-001",
        "invoice_date": "2024-03-03",
        "po_number": "PO-2024-002",
        "currency": "USD",
        "payment_terms": "Net 45",
        "subtotal": 2250.00,
        "tax_amount": 180.00,
        "total_amount": 2430.00,
        "line_items": [
            {
                "sku": "SKU-MONITOR-27",
                "description": "27-inch 4K UHD Monitor",
                "quantity": 50.0,
                "unit_price": 45.00,
                "tax_rate": 0.08,
                "line_total": 2250.00
            }
        ]
    }
    files = {"file": ("inv_mismatch.json", json.dumps(invoice_3_data), "application/json")}
    res = client.post("/api/invoices/upload", files=files)
    assert res.status_code == 200
    inv_3_res = res.json()
    inv_3_id = inv_3_res["id"]
    print(f"Mismatch invoice status: {inv_3_res['status']}")
    assert inv_3_res['status'] == "EXCEPTION"
    
    receipt_ctrl = next((c for c in inv_3_res.get('controls', []) if c['control_type'] == 'RECEIPT_VERIFICATION'), None)
    assert receipt_ctrl is not None and receipt_ctrl['status'] == 'FAILED'
    print(f"Receipt control correctly failed: {receipt_ctrl['details']}")

    # Inspect Exceptions
    res = client.get(f"/api/invoices/{inv_3_id}")
    inv_3_detail = res.json()
    exceptions = inv_3_detail.get("exceptions", [])
    assert len(exceptions) >= 1
    exc = exceptions[0]
    print(f"Open Exception: ID={exc['id']}, Type={exc['type']}, Message={exc['message']}")

    # Test Exception Reassign
    print_step("5b. Reassigning Exception")
    res = client.post(f"/api/exceptions/{exc['id']}/reassign", json={"assigned_to": "AuditLead", "notes": "Reassigned for discrepancy review"})
    assert res.status_code == 200
    print(f"Reassigned successfully: {res.json()['assigned_to_name']}")

    # Test Exception Override (Mandatory Reason Required)
    print_step("5c. Overriding Exception with Audit Justification")
    res = client.post(f"/api/exceptions/{exc['id']}/override", json={
        "override_reason": "Approved by VP Supply Chain: 20 remaining units delivered to warehouse annex per Bill of Lading BL-4492."
    })
    assert res.status_code == 200
    print(f"Override result: {res.json()}")

    # Check that original failure is preserved and invoice moved to APPROVED or PENDING_REVIEW
    res = client.get(f"/api/invoices/{inv_3_id}")
    inv_3_after = res.json()
    print(f"Invoice 3 status after override: {inv_3_after['status']}")
    # Original control must still show FAILED in control results
    ctrl_after = next((c for c in inv_3_after.get('controls', []) if c['control_type'] == 'RECEIPT_VERIFICATION'), None)
    assert ctrl_after['status'] == 'FAILED', "Override must preserve the original failed control result!"
    print("Original failed control result successfully preserved in history!")

    # 6. Test Case 4: Duplicate Invoice Detection
    print_step("6. Test Case 4: Duplicate Invoice Detection")
    files = {"file": ("inv_acme_dup.json", json.dumps(invoice_1_data), "application/json")}
    res = client.post("/api/invoices/upload", files=files)
    assert res.status_code == 200
    inv_4_res = res.json()
    print(f"Duplicate invoice status: {inv_4_res['status']}")
    dup_ctrl = next((c for c in inv_4_res.get('controls', []) if c['control_type'] == 'DUPLICATE_DETECTION'), None)
    assert dup_ctrl is not None and dup_ctrl['status'] == 'FAILED'
    print(f"Duplicate detection correctly caught: {dup_ctrl['details']}")

    # 7. Test Case 5: Payable Ledger Settlement
    print_step("7. Test Case 5: Payable Ledger & Settlement")
    res = client.get("/api/ledger")
    assert res.status_code == 200
    ledger_items = res.json()
    print(f"Found {len(ledger_items)} obligations in ledger")
    target_payable = next((p for p in ledger_items if p["id"] == payable_id), None)
    assert target_payable is not None, f"Payable {payable_id} not found in ledger"
    assert target_payable["status"] == "UNPAID"

    # Settle Payable
    res = client.post(f"/api/ledger/{payable_id}/pay", json={
        "settlement_reference": "ACH-CITI-2024-998811",
        "notes": "Bank ACH batch transfer completed"
    })
    assert res.status_code == 200
    paid_payable = res.json()
    print(f"Settled payable: Status={paid_payable['status']}, Paid At={paid_payable['paid_at']}, Ref={paid_payable['settlement_reference']}")
    assert paid_payable["status"] == "PAID"

    # 8. Test Case 6: Dynamic Dashboard Verification
    print_step("8. Test Case 6: Dynamic Dashboard Aggregations")
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    dash = res.json()
    print("Dashboard Metrics:")
    for k, v in dash.items():
        if k not in ["recent_invoices", "pending_approvals", "open_exceptions"]:
            print(f" - {k}: {v}")
    assert dash["total_invoices"] >= 3, f"Expected at least 3 invoices, got {dash['total_invoices']}"
    assert dash["total_payable_amount"] > 0, "Payable amount should reflect settled/active obligations"

    # 9. Test Case 7: Complete Audit Trail Verification
    print_step("9. Test Case 7: Audit Trail Verification")
    res = client.get("/api/audit")
    assert res.status_code == 200
    audit_events = res.json()
    print(f"Total recorded audit events in DB: {len(audit_events)}")
    actions = [a["action"] for a in audit_events]
    print(f"Distinct actions logged: {set(actions)}")
    
    assert "INVOICE_UPLOADED" in actions
    assert "CONTROL_EXECUTED" in actions
    assert "APPROVAL_GRANTED" in actions
    assert "PAYABLE_CREATED" in actions
    assert "EXCEPTION_OVERRIDDEN" in actions
    assert "PAYABLE_PAID" in actions
    print("All critical FIN-06 state transitions verified in database audit trail!")

    print_step("ALL E2E AP LIFECYCLE TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\n❌ E2E TEST FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
