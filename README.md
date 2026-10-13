# Litmus — Multi-Agent Debugging Courtroom System

A full-stack multi-agent debugging system featuring an adversarial courtroom debate (Prosecutor, Defender, Judge) with deterministic sandboxed test evaluation, constraint persistence, and an interactive real-time visualizer frontend.

---

## Architecture Overview

- **Frontend (`/src`, `/public`)**: React + TypeScript + Vite interactive courtroom visualizer and battle interface.
- **Backend (`/Litmus/Backend`)**: Python-based multi-agent orchestration (LangGraph, local Ollama LLM), sandboxed execution runner, JUnit XML deterministic test evaluator, and SQLite constraint ledger.

---

## Frontend Setup (React + TypeScript + Vite)

```bash
npm install
npm run dev
```

## Backend Setup (Python)

```bash
cd Litmus/Backend
pip install -r requirements.txt
python -m pytest tests/ -v
```
