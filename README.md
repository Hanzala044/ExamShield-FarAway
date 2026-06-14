# 🛡️ ExamShield: Centralized Exam Integrity Infrastructure

<p align="center">
  <b>Secure • Transparent • Tamper-Proof</b><br>
  <i>Secure computer-based test infrastructure — time-locked encrypted paper distribution, biometric identity verification, autonomous AI fraud detection, and an immutable on-chain audit trail for India's national examinations.</i>
</p>

---

## 🏛️ Architectural Diagram

![Architectural Diagram](./architecture.jpg)

> **Note:** Ensure the architecture image is saved as `architecture.jpg` in the root directory.

---

## ✨ Key Features & Lifecycle

### 1. Setup & Secure Paper Distribution (Before Exam)
- **Paper Creation:** Admin creates the exam and uploads the paper.
- **AES-256-GCM Encryption:** The paper is encrypted before distribution.
- **Key Split (XOR):** The encryption key is split into two halves. One half is stored in a Server Key Vault, and the other is locked in a Time-Lock Contract on the blockchain.
- **Paper Distributed:** The usable ciphertext is distributed to exam centers, and a `PaperDistributed` event is logged on-chain.

### 2. Identity Verification (Check-in)
- **Face Capture & Liveness:** Student arrives and their face is matched against records using **VerifyGate**.
- **Auto Check-in:** A score $\ge 0.85$ results in automatic check-in.
- **Manual Override:** A score $< 0.85$ denies access, requiring manual override with mandatory reasoning.
- **On-chain Logging:** A `StudentCheckedIn` event is logged on the blockchain.

### 3. Key Release & Session Opening
- **Time-lock + Geofence:** At the exam start time, verification checks if the GPS is inside the geofence and the time-lock is reached.
- **Key Assembly:** The time-lock contract releases the key half, which combines with the server's half in memory.
- **Decryption:** The paper is decrypted in memory.
- **Session Opened:** A `SessionOpened` event is logged on-chain.

### 4. During Exam (Live Monitoring)
- **Student Kiosk:** A locked browser ensures test integrity.
- **Telemetry Stream:** Answers, time taken, tab switches, and IP addresses are streamed live.
- **IntegrityAI Engine:** AI rules and ML models monitor telemetry to flag anomalies.
- **Live Alerts:** Invigilators receive real-time anomaly alerts via WebSockets.
- **Anomaly Flagged:** A `AnomalyFlagged` event is logged on-chain.

### 5. Session Closure & Post Exam
- **Answers Captured:** Timer ends, student submits, answers are captured and checksummed.
- **Secure Storage:** Data is encrypted and sent to storage.
- **Session Closed:** A `SessionClosed` event is logged on-chain.

### 6. Post-Exam Fraud Analysis
- **Run Fraud Analysis:** Admin triggers cross-submission analysis.
- **Clustering & Networks:** Detects identical wrong answers, builds a force-directed network graph, and ranks suspects.
- **Analysis Complete:** `AnalysisComplete` event logged on-chain.

### 7. Public Verification
- **Polygon Blockchain:** All critical events are written to an immutable ledger.
- **Publicly Queryable Audit Trail:** Anyone can verify events by hash without logging in, ensuring a tamper-proof record.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Encryption** | AES-256-GCM |
| **Blockchain** | Polygon PoS |
| **Backend** | FastAPI (Python) |
| **AI / ML** | Claude API |
| **Frontend** | React Native / React (Vite/TS) |
| **Database** | PostgreSQL |
| **Storage** | AWS S3 (Encrypted) |
| **Real-time** | WebSocket (WSS) |
| **Hosting** | AWS / On-Prem |

---

## 🚀 Quick Start (Docker)

```bash
docker compose up --build
```

- **Frontend** → http://localhost:5173
- **Backend API + docs** → http://localhost:8000/docs
- **Public audit trail** → http://localhost:5173/audit (no login required)

*The database auto-seeds on first boot with 3 centers, 50 students, and 2 exams.*

### 🔑 Demo Accounts

| User | Password | Role |
|---|---|---|
| `admin` | `admin123` | NTA Super Admin |
| `coord1` / `coord2` / `coord3` | `coord123` | Center Coordinator (Delhi / Mumbai / Pune) |
| `invig1` | `invig123` | Invigilator |

---

## 💻 Running Without Docker

**Backend** (Requires local PostgreSQL or a `DATABASE_URL`):
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

---

## 🌐 Going to Production

- **Polygon:** Implement `services/ledger.record()` against a deployed Solidity contract via `web3/ethers`; set `CHAIN_SIMULATED=false`.
- **Face API:** Replace `services/face.compare()` with AWS Rekognition or Azure Face.
- **Claude API:** Set `AI_USE_CLAUDE=true` and provide `ANTHROPIC_API_KEY`; implement the call in `services/integrity.narrate()`.
