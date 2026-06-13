import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .routers import (
    auth as auth_router,
    centers as centers_router,
    exam_session as session_router,
    exams as exams_router,
    fraud as fraud_router,
    ledger as ledger_router,
    ws as ws_router,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("examshield")

app = FastAPI(
    title="ExamShield API",
    version="1.0.0",
    description="Secure CBT infrastructure — PaperVault, VerifyGate, ExamKiosk, "
                "IntegrityAI, ChainLedger.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(exams_router.router)
app.include_router(centers_router.router)
app.include_router(session_router.router)
app.include_router(fraud_router.router)
app.include_router(ledger_router.router)
app.include_router(ws_router.router)


@app.get("/")
def root():
    return {"service": "ExamShield API", "status": "ok",
            "docs": "/docs", "audit": "/audit/events"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    from . import seed
    db = SessionLocal()
    try:
        seed.run(db)
    finally:
        db.close()
    log.info("ExamShield startup complete.")
