# Litmus — Multi-Agent Courtroom Debugger Backend

Litmus is an adversarial multi-agent courtroom debugging engine powered by LangGraph, local Ollama models (`qwen2.5-coder:7b`), and isolated execution sandboxes.

---

## 1. Courtroom Architecture & Roles

- **Prosecutor (`app/agents/prosecutor.py`):** Diagnoses reported bugs, formulates accusations, and generates Fix A.
- **Defender (`app/agents/defender.py`):** Critically attacks Prosecutor claims, explores edge cases, and proposes Fix B.
- **Judge (`app/agents/judge.py`):** Delivers evidence-grounded verdicts based strictly on empirical sandbox test results.
- **Sandbox Runner (`app/sandbox/runner.py`):** Executes candidate solutions against trusted pytest suites in isolated Docker or host environments.
- **Deterministic Evaluator (`app/evaluation/test_evaluator.py`):** Converts execution outputs and JUnit XML into immutable `TestResult` records.
- **Constraint Ledger (`app/memory/constraint_ledger.py`):** Records failure signatures and rejected code snippets to prevent repeated mistakes across retry rounds.
- **FastAPI Server (`app/api/server.py`):** Exposes REST APIs, idempotent run execution, and Server-Sent Events (SSE) streaming with event replay.

---

## 2. Installation & Setup

### Prerequisites
- Python 3.10+
- (Optional but recommended) Docker for sandboxed candidate execution
- (Optional for local inference) Ollama

### Step 1: Install Dependencies
```bash
cd Litmus/Backend
python -m venv .venv

# Windows Powershell
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Build Sandbox Docker Image
If using Docker for secure isolated execution:
```bash
docker build -t litmus-sandbox sandbox
```
*(If Docker is not running or unavailable, set `SWARM_ALLOW_HOST_EXECUTION=1` in your environment to allow fallback to host Python).*

### Step 3: Setup Local Ollama Model
```bash
ollama pull qwen2.5-coder:7b
```

---

## 3. Running the Server

Run from the `Litmus/Backend` directory:
```bash
uvicorn app.api.server:app --reload --port 8000
```
API endpoints will be available at `http://127.0.0.1:8000`.

---

## 4. Environment Variables

Configure via `Litmus/Backend/.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint for local Ollama server |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Default LLM model identifier |
| `OLLAMA_NUM_CTX` | `8192` | Context window token limit |
| `OLLAMA_NUM_PREDICT` | `4096` | Max output token generation limit |
| `OLLAMA_KEEP_ALIVE` | `10m` | Model memory retention duration |
| `OLLAMA_TIMEOUT_SECONDS` | `300.0` | HTTP request timeout for LLM inference |
| `GEMINI_API_KEY` | `""` | Optional Google Gemini API key |
| `SWARM_ALLOW_HOST_EXECUTION` | `1` | Allow fallback to host python sandbox when Docker is absent |
| `SWARM_SANDBOX_TIMEOUT_SECONDS` | `30.0` | Execution timeout per sandbox test run |
| `SANDBOX_DOCKER_IMAGE` | `litmus-sandbox:latest` | Docker image for isolated sandbox |
| `DATABASE_PATH` | `litmus.db` | SQLite database file path |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173` | Allowed frontend origins |

---

## 5. Running Tests

Run the full verification test suite (unit and integration):
```bash
cd Litmus/Backend
python -m pytest tests -q
```
All unit and integration tests run offline without requiring a live Ollama connection or network calls.
