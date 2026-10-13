# Litmus — Multi-Agent Debugging Courtroom System

A full-stack multi-agent debugging system featuring an adversarial courtroom debate (Prosecutor, Defender, Judge) with deterministic sandboxed test evaluation, constraint persistence, and an interactive real-time visualizer frontend.

---

## Project Structure

```
Litmus/
├── Frontend/         # React + TypeScript + Vite courtroom UI
└── Litmus/Backend/   # Python LangGraph agents, execution sandbox, & SQLite ledger
```

---

## Frontend Setup (React + TypeScript + Vite)

```bash
cd Frontend
npm install
npm run dev
```

## Backend Setup (Python)

```bash
cd Litmus/Backend
pip install -r requirements.txt
python -m pytest tests/ -v
```
