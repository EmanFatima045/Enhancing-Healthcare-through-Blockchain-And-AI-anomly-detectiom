"""
HealerPlus - Main FastAPI Application
Enhancing Healthcare Security Using Blockchain and AI
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import time
from sqlalchemy import func, select, text

from .core.config import settings
from .api.auth import router as auth_router
from .api.records import router as records_router
from .api.ids_security import router as security_router
from .api.iomt import router as iomt_router
from .api.federated import router as federated_router
from .api.appointments import router as appointments_router
from .api.blockchain import router as blockchain_router
from .api.audit import router as audit_router
from .api.notifications import router as notifications_router
from .api.operations import router as operations_router
from .services.blockchain_service import blockchain_service
from .core.database import SessionLocal, initialize_database
from .models import OutboxJob


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    initialize_database()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Healthcare security academic project with explicit real, simulated, and unavailable capability states",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith(settings.API_V1_STR):
        response.headers.setdefault("Cache-Control", "no-store")
    return response

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(records_router, prefix=settings.API_V1_STR)
app.include_router(security_router, prefix=settings.API_V1_STR)
app.include_router(iomt_router, prefix=settings.API_V1_STR)
app.include_router(federated_router, prefix=settings.API_V1_STR)
app.include_router(appointments_router, prefix=settings.API_V1_STR)
app.include_router(blockchain_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(operations_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "timestamp": time.time(),
        "blockchain": blockchain_service.get_blockchain_overview(),
        "capabilities": {"database": "REAL", "ai_ids": "LOCAL_DEVELOPMENT_MODEL",
                         "iomt": "SIMULATED", "federated_learning": "SIMULATED",
                         "blockchain": "CONFIGURATION_DEPENDENT", "ipfs": "UNAVAILABLE"},
        "docs_url": "/docs"
    }

@app.get(f"{settings.API_V1_STR}/health")
async def health():
    return {"status": "OPERATIONAL", "version": settings.VERSION}


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics():
    """Small dependency-free Prometheus endpoint for local and container monitoring."""
    with SessionLocal() as db:
        pending = db.scalar(select(func.count()).select_from(OutboxJob).where(
            OutboxJob.status.in_(["PENDING", "RETRY", "SUBMITTED"]))) or 0
        failed = db.scalar(select(func.count()).select_from(OutboxJob).where(
            OutboxJob.status == "FAILED")) or 0
    return ("# HELP healerplus_up API process health\n"
            "# TYPE healerplus_up gauge\n"
            "healerplus_up 1\n"
            "# HELP healerplus_outbox_pending_jobs Durable outbox jobs awaiting completion\n"
            "# TYPE healerplus_outbox_pending_jobs gauge\n"
            f"healerplus_outbox_pending_jobs {pending}\n"
            "# HELP healerplus_outbox_failed_jobs Durable outbox jobs exhausted retries\n"
            "# TYPE healerplus_outbox_failed_jobs gauge\n"
            f"healerplus_outbox_failed_jobs {failed}\n")


@app.get(f"{settings.API_V1_STR}/health/ready")
def readiness():
    """Deployment readiness probe with dependency state, not just process liveness."""
    checks = {"database": {"status": "UNKNOWN"}, "outbox_storage": {"status": "UNKNOWN"},
              "blockchain": blockchain_service.health()}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            checks["database"] = {"status": "READY"}
            pending = db.scalar(select(func.count()).select_from(OutboxJob).where(OutboxJob.status.in_(["PENDING", "RETRY", "SUBMITTED"]))) or 0
            failed = db.scalar(select(func.count()).select_from(OutboxJob).where(OutboxJob.status == "FAILED")) or 0
            checks["outbox_storage"] = {"status": "READY", "pending_jobs": pending, "failed_jobs": failed}
    except Exception as exc:
        checks["database"] = {"status": "UNAVAILABLE", "error": type(exc).__name__}
        checks["outbox_storage"] = {"status": "UNAVAILABLE"}
    ready = checks["database"]["status"] == "READY"
    payload = {"status": "READY" if ready else "NOT_READY", "checks": checks}
    return JSONResponse(payload, status_code=200 if ready else 503)

@app.get(f"{settings.API_V1_STR}/blockchain/explorer")
async def blockchain_explorer():
    return blockchain_service.get_blockchain_overview()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
