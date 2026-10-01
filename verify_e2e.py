"""
E2E invoice processing test - SQLite local architecture
"""
import urllib.request
import urllib.error
import json
import uuid
import sys

BASE = "http://localhost:8000"


def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "msg": e.read().decode()}


def upload_invoice(invoice_json_bytes, filename="test_invoice.json"):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + invoice_json_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE}/api/invoices/upload",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "msg": e.read().decode()}


def main():
    print("=" * 60)
    print("PayGuard E2E Test - SQLite Local Architecture")
    print("=" * 60)

    # 1. Health check
    health = api("GET", "/health")
    print(f"\n1. Health: {health}")
    assert health.get("status") == "healthy", "Backend not healthy!"

    # 2. Check existing vendors
    vendors = api("GET", "/api/master/vendors")
    print(f"\n2. Vendors in DB: {[(v['id'], v['name'], v['status']) for v in vendors]}")
    assert len(vendors) > 0, "No vendors found - check seed data"

    # Find active vendor
    active_vendor = next((v for v in vendors if v["status"] == "ACTIVE"), None)
    assert active_vendor, "No active vendor found"
    print(f"   Using vendor: {active_vendor['name']} (id={active_vendor['id']})")

    # 3. Check POs
    pos = api("GET", "/api/master/purchase-orders")
    print(f"\n3. POs in DB: {[(p['id'], p['po_number'], p['status']) for p in pos]}")
    assert len(pos) > 0, "No POs found"

    # Find a received PO for active vendor
    matching_po = next(
        (p for p in pos if p["status"] in ("RECEIVED", "PARTIALLY_RECEIVED")), None
    )
    assert matching_po, "No received PO found"
    print(f"   Using PO: {matching_po['po_number']} (id={matching_po['id']})")

    # 4. Upload invoice that should match vendor + PO
    inv_num = f"INV-{uuid.uuid4().hex[:8].upper()}"
    invoice_payload = {
        "invoice_number": inv_num,
        "vendor": {
            "name": active_vendor["name"],
            "tax_id": active_vendor.get("tax_id", ""),
        },
        "po_number": matching_po["po_number"],
        "invoice_date": "2024-10-01",
        "due_date": "2024-10-31",
        "currency": "USD",
        "payment_terms": "Net 30",
        "subtotal": 4500.00,
        "tax_amount": 360.00,
        "total_amount": 4860.00,
        "line_items": [
            {
                "description": "Widget Pro Model A",
                "sku": "WID-A",
                "quantity": 100,
                "unit_price": 40.00,
                "tax_rate": 0.08,
                "line_total": 4000.00,
            },
            {
                "description": "Premium Service Package",
                "sku": "SVC-P",
                "quantity": 5,
                "unit_price": 100.00,
                "tax_rate": 0.08,
                "line_total": 500.00,
            },
        ],
        "confidence": 0.95,
    }

    print(f"\n4. Uploading invoice {inv_num}...")
    result = upload_invoice(json.dumps(invoice_payload).encode())
    print(f"   Result: {json.dumps(result, indent=4)}")
    assert "invoice_id" in result, f"Upload failed: {result}"
    invoice_id = result["invoice_id"]
    print(f"   Invoice ID: {invoice_id}, Status: {result['status']}")
    print(f"   Control Decision: {result['control_result'].get('decision')}")

    # 5. Fetch invoice detail
    print(f"\n5. Fetching invoice {invoice_id} detail...")
    detail = api("GET", f"/api/invoices/{invoice_id}")
    print(f"   Status: {detail['status']}")
    print(f"   Controls: {[(c['control_name'], c['status']) for c in detail['control_results']]}")
    print(f"   Exceptions: {[(e['type'], e['status']) for e in detail['exceptions']]}")
    print(f"   Approvals: {[(a['level'], a['status']) for a in detail['approvals']]}")
    print(f"   Payable: {detail['payable_obligation']}")

    # 6. Dashboard after processing
    print("\n6. Dashboard metrics:")
    dash = api("GET", "/api/dashboard")
    summary = dash.get("summary", {})
    print(f"   Total invoices: {summary.get('total_invoices')}")
    print(f"   Pending review: {summary.get('pending_review')}")
    print(f"   Approved: {summary.get('approved')}")
    print(f"   Exceptions: {summary.get('total_exceptions')}")

    print("\n" + "=" * 60)
    print("E2E TEST PASSED - Invoice processed end-to-end successfully!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
