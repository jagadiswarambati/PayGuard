# FIN-06 Quick Start Guide

## 🚀 Starting the Application

### 1. Start Database (Terminal 1)
```bash
docker-compose up
```

### 2. Start Backend (Terminal 2)
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be at: **http://localhost:8000**
API docs at: **http://localhost:8000/docs**

### 3. Start Frontend (Terminal 3)
```bash
cd frontend
npm install
npm run dev
```

Frontend will be at: **http://localhost:3000**

## ✅ What's Included

### Backend Features
- ✓ PostgreSQL database with full relational schema
- ✓ NOVA API integration for invoice extraction (key configured in .env)
- ✓ Complete control engine with ±5% tolerance
- ✓ Vendor verification
- ✓ PO matching
- ✓ Goods receipt verification
- ✓ Duplicate detection
- ✓ Financial validation
- ✓ Approval workflow engine
- ✓ Exception management
- ✓ Payable ledger
- ✓ Complete audit trail
- ✓ RESTful API with FastAPI

### Frontend Features
- ✓ Professional enterprise dashboard
- ✓ Invoice upload and processing
- ✓ Real-time control results
- ✓ Exception management UI
- ✓ Approval workflow UI
- ✓ Payable ledger tracking
- ✓ Audit trail viewer
- ✓ Responsive design with Tailwind CSS
- ✓ TypeScript for type safety

## 🎯 Key Flows

### Invoice Processing Flow
1. **Upload Invoice** → `/invoices/upload`
2. **NOVA Extracts Data** → Automatic AI extraction
3. **Store in Database** → PostgreSQL persistence
4. **Run Controls**:
   - Vendor verification
   - PO matching (±5% tolerance)
   - Receipt verification
   - Duplicate detection
   - Financial validation
5. **Decision**:
   - ✓ Pass → Approval workflow
   - ✗ Fail → Exception management
6. **Approval** → Based on amount thresholds
7. **Payable Created** → Automatic after approval
8. **Audit Logged** → Complete traceability

## 🔧 Configuration

All configuration in `.env` file:
- ✓ NOVA API key: **CONFIGURED**
- ✓ Database URL: **localhost:5432**
- ✓ Tolerances: **±5% price and quantity**
- ✓ Approval thresholds:
  - < $5,000: Auto-approve
  - $5,000-$25,000: Medium approval
  - ≥ $25,000: High approval

## 📊 Dynamic Data

**ZERO HARDCODED BUSINESS DATA**
- All metrics calculated from database
- Empty states shown when no data exists
- All dashboard numbers are real-time
- Control results determined by actual data
- Exceptions created dynamically
- Approvals based on real thresholds
- Payable ledger reflects actual obligations

## 🧪 Optional: Seed Test Data

To create test data for development:
```bash
cd backend
python -c "from app.db.seed import create_seed_data; from app.database import SessionLocal; db = SessionLocal(); create_seed_data(db); db.close()"
```

This creates:
- Sample vendors (including one blocked vendor)
- Purchase orders with items
- Goods receipts (including partial receipt)
- Realistic test scenarios

## 🔐 Security

- ✓ NOVA API key in backend environment only
- ✓ Never exposed to frontend
- ✓ .env file in .gitignore
- ✓ .env.example provided for setup
- ✓ CORS configured for localhost development

## 📝 API Endpoints

- `GET /api/dashboard` - Dashboard metrics
- `POST /api/invoices/upload` - Upload invoice
- `GET /api/invoices` - List invoices
- `GET /api/invoices/{id}` - Invoice details
- `GET /api/exceptions` - List exceptions
- `POST /api/exceptions/{id}/resolve` - Resolve exception
- `GET /api/approvals` - List approvals
- `POST /api/approvals/{id}/approve` - Approve invoice
- `GET /api/ledger` - Payable obligations
- `GET /api/audit` - Audit events

## 🎉 You're Ready!

The system is now running end-to-end:
1. Upload an invoice PDF/PNG/JPG
2. Watch NOVA extract the data
3. See control engine validate
4. Review exceptions or approvals
5. Track in payable ledger
6. View complete audit trail

**Everything works with REAL data - no mocks, no fakes!**
