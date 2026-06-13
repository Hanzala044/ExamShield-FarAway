# ExamShield

**Secure computer-based test infrastructure** — time-locked encrypted paper
distribution, biometric identity verification, autonomous AI fraud detection, and
an immutable on-chain audit trail for India's national examinations.

Built for the *Far Away 2026 — Examinations* track. This is a fully runnable
hackathon MVP of the [PRD](#modules): all three role interfaces + the FastAPI
backend, real AES-256-GCM split-key encryption, a hash-chained audit ledger, and
a deterministic fraud-analysis engine.

> **What's real vs simulated in this build**
> | Real | Simulated (swappable via env) |
> |---|---|
> | AES-256-GCM split-key paper encryption | Polygon chain → local hash-chained ledger (`/audit`) |
> | Time-lock + GPS geofence key release | Cloud Face API → deterministic match score |
> | Statistical fraud detection + network graph | Claude evidence prose → templated notes |
> | 5-role JWT RBAC, WebSocket live alerts | |
>
> Every simulation is isolated behind a service module with a documented swap
> point, so it can be pointed at the real Polygon/Rekognition/Claude without
> touching application code.

---

## Quick start (Docker)

```bash
docker compose up --build
```

- **Frontend** → http://localhost:5173
- **Backend API + docs** → http://localhost:8000/docs
- **Public audit trail** → http://localhost:5173/audit (no login)

The database auto-seeds on first boot (3 centers, 50 students, 2 exams).

### Demo accounts
| User | Password | Role |
|---|---|---|
| `admin` | `admin123` | NTA Super Admin |
| `coord1` / `coord2` / `coord3` | `coord123` | Center Coordinator (Delhi / Mumbai / Pune) |
| `invig1` | `invig123` | Invigilator |

---

## 3-minute demo script

1. **NTA Admin** (`admin`) → *NTA Admin* tab. Create an exam (starts in 2 min):
   the paper is encrypted with AES-256-GCM on upload and its `blobHash` appears.
   Click **Distribute** → a `PaperDistributed` event is written on-chain.
2. **Coordinator** (`coord1`) → *Center Console*. Check in a student by roll no
   (`NEET2026-0001`) — **VerifyGate** returns a face-match score and issues a
   session token. Try `NEET2026-0005` (a seeded impersonator) to trigger the
   **manual override** path — both outcomes are logged on-chain.
3. Click **Release Time-Locked Key**. The server enforces the time-lock + GPS
   geofence before reassembling the split key and decrypting the paper.
   (`KeyReleased` + `SessionOpened` on-chain.)
4. **Student Kiosk** → open http://localhost:5173/kiosk, paste the session token.
   Take the exam. Answer a **hard** question in under 2 seconds, or switch
   browser tabs — watch the **live anomaly alert** appear on the Coordinator's
   feed in real time. Submit.
5. **NTA Admin** → run **Fraud Analysis** on *"NEET-UG 2026 — Biology
   (Completed)"*. IntegrityAI surfaces the two planted collusion clusters with a
   force-directed **network graph** and ranked evidence. `AnalysisComplete`
   on-chain.
6. **Public Audit** (`/audit`) → anyone can browse the hash-chained ledger,
   verify any event by its hash, and confirm chain integrity — no login.

---

## Architecture

```
React (Vite/TS)  ──HTTPS/WS──►  FastAPI (Python 3.12)  ──►  PostgreSQL 16
  Admin Portal                    • JWT 5-role RBAC          (exams, students,
  Center Console                  • WebSocket live feed       submissions, flags)
  Student Kiosk                   • PaperVault (AES-GCM)
  Public Audit                    • VerifyGate (face)    ──►  ChainLedger
                                  • IntegrityAI (fraud)       (hash-chained,
                                                               public read API)
```

### Modules (PRD §05)
| | Module | Implementation |
|---|---|---|
| M1 | **PaperVault** | `services/crypto.py` — AES-256-GCM, XOR split key, time-lock + geofence release |
| M2 | **CenterOS** | `routers/centers.py` + Center Console UI — check-in, session lifecycle |
| M3 | **VerifyGate** | `services/face.py` — deterministic match, on-chain non-repudiation |
| M4 | **ExamKiosk** | `pages/kiosk` — locked browser, palette, timer, telemetry stream |
| M5 | **IntegrityAI** | `services/integrity.py` — live rules + post-exam clustering + graph |
| M6 | **ChainLedger** | `services/ledger.py` + `routers/ledger.py` — 8 event types, public verify |

---

## Running without Docker

**Backend** (needs a local PostgreSQL, or set `DATABASE_URL`):
```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://examshield:examshield@localhost:5432/examshield
uvicorn app.main:app --reload
```

**Frontend**:
```bash
cd frontend
npm install
VITE_API_BASE=http://localhost:8000 npm run dev
```

## Going to production
- **Polygon**: implement `services/ledger.record()` against a deployed Solidity
  contract via web3/ethers; set `CHAIN_SIMULATED=false`.
- **Face**: replace `services/face.compare()` with AWS Rekognition / Azure Face.
- **Claude**: set `AI_USE_CLAUDE=true` + `ANTHROPIC_API_KEY`; implement the call
  in `services/integrity.narrate()` (single swap point).
