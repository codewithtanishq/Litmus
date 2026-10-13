# Litmus — Multi-Agent Debugging Courtroom System

A full-stack multi-agent debugging system featuring an adversarial courtroom debate (Prosecutor, Defender, Judge) with deterministic sandboxed test evaluation, constraint persistence, and an interactive real-time visualizer frontend.

---

## Project Structure

`
Litmus/
├── src/              # React + TypeScript + Vite courtroom UI
└── Litmus/Backend/   # Python LangGraph agents, execution sandbox, & SQLite ledger
`

---

## Frontend Setup (React + TypeScript + Vite)

`ash
npm install
npm run dev
`

## Backend Setup (Python)

`powershell
cd Litmus/Backend
 = D:\3rd sem\Projects\HACKTOPIA\Litmus\Litmus
python -m pytest tests/ -v
`
