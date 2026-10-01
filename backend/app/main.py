from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .api import dashboard, invoices, exceptions, approvals, ledger, audit, settings as settings_api, master_data
from .api import nova_dataset

app = FastAPI(
    title="PayGuard — AI-Powered Accounts Payable Control",
    version="2.0.0",
    description=(
        "PayGuard receives invoice data from the NOVA external dataset or uploaded documents. "
        "Its intelligence layer reconciles evidence against procurement and receipt records. "
        "Its deterministic control engine verifies each transaction. "
        "Exceptions are routed for review. Approvals enforced. Only validated obligations enter the payable ledger."
    ),
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard.router)
app.include_router(invoices.router)
app.include_router(exceptions.router)
app.include_router(approvals.router)
app.include_router(ledger.router)
app.include_router(audit.router)
app.include_router(settings_api.router)
app.include_router(master_data.router)
app.include_router(nova_dataset.router)


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/")
def root():
    return {
        "product": "PayGuard",
        "tagline": "AI-Powered Accounts Payable Control",
        "version": "2.0.0",
        "status": "running",
        "architecture": {
            "data_source": "NOVA API (external pre-dataset)",
            "intelligence": "PayGuard (entity resolution, anomaly detection, risk scoring)",
            "controls": "PayGuard (vendor, PO, receipt, duplicate, financial, GST)",
            "decisions": "PayGuard (approval workflow, exception routing, payable ledger)",
        },
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "product": "PayGuard"}
