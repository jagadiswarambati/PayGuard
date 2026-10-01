from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .api import dashboard, invoices, exceptions, approvals, ledger, audit, settings as settings_api, master_data

app = FastAPI(title="FIN-06 AP Control System", version="1.0.0")

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


@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def root():
    return {"message": "FIN-06 AP Control System API", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
