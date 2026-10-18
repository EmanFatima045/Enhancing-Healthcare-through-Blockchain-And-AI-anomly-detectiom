"""
HealerPlus 2.0 - Main FastAPI Application
Enhancing Healthcare Security Using Blockchain and AI
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time

from .core.config import settings
from .api.auth import router as auth_router
from .api.records import router as records_router
from .api.ids_security import router as security_router
from .api.iomt import router as iomt_router
from .api.federated import router as federated_router
from .api.appointments import router as appointments_router
from .api.blockchain import router as blockchain_router
from .services.blockchain_service import blockchain_service
from .core.database import initialize_database


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

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(records_router, prefix=settings.API_V1_STR)
app.include_router(security_router, prefix=settings.API_V1_STR)
app.include_router(iomt_router, prefix=settings.API_V1_STR)
app.include_router(federated_router, prefix=settings.API_V1_STR)
app.include_router(appointments_router, prefix=settings.API_V1_STR)
app.include_router(blockchain_router, prefix=settings.API_V1_STR)

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

@app.get(f"{settings.API_V1_STR}/blockchain/explorer")
async def blockchain_explorer():
    return blockchain_service.get_blockchain_overview()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
