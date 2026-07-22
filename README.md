# Social Support AI — Eligibility Assessment Prototype

An AI-powered prototype that automates intake, validation, and eligibility
assessment for government social/financial support applications.

## Architecture

- **Orchestrator**: master planning agent that inspects available documents
  and builds an execution plan before dispatching sub-agents (`app/agents/orchestrator.py`)
- **Ingestion**: extracts structured data from bank statements, credit reports,
  Emirates ID, resume, and assets/liabilities spreadsheets (`app/ingestion/`)
- **Storage**: PostgreSQL (structured fields), MongoDB (raw document content),
  Qdrant (semantic embeddings), Neo4j (relationship graph — household/family links)
- **Agents**: multi-agent pipeline (orchestrator → extraction → validation →
  eligibility → decision) built with LangGraph (`app/agents/`)
- **Observability**: every agent step is traced (input/output/duration) via
  Langfuse if configured, otherwise to a local JSONL log (`app/observability/`)
- **API**: FastAPI backend (`app/api/`)
- **Frontend**: Streamlit chat interface (`frontend/`)

## Setup

### 1. Start the databases
```bash
docker compose up -d
```

### 2. Python environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Initialize the database schema
```bash
python -m app.db.init_db
```

### 4. Verify all databases are reachable
```bash
python -m app.db.connections
```
Expect `OK` for postgres, mongodb, qdrant, and neo4j.

### 5. Pull the local LLM (requires Ollama installed separately)
```bash
ollama pull llama3
```

## Test data

Synthetic applicant document sets are in `data/synthetic/`:
- `applicant_1/` — mid-income, borderline case (bank statement, credit report,
  Emirates ID, assets/liabilities, resume)
- `applicant_2/` — low-income, clearly eligible case
- `applicant_3/` — high-income, clearly ineligible case

Each applicant folder includes a `resume.pdf` used to extract real employment
status, years of employment, and family size — these are no longer hardcoded
defaults; if a resume is missing for a given applicant, the pipeline falls
back to conservative defaults and this is explicitly logged.

`data/synthetic/eligibility_training_data.csv` — 300-row synthetic dataset
for training the eligibility classification model.

## Running the ingestion pipeline (Phase 1)

```bash
python -m app.ingestion.pipeline data/synthetic/applicant_1
```

This extracts, combines, and stores one applicant's full document set into
PostgreSQL + MongoDB, printing the structured record to console.

## Running validation (Phase 2)

```bash
python -m app.agents.validation data/synthetic/applicant_1
```

## Training the eligibility model (Phase 3)

```bash
python -m app.agents.eligibility_model
```

Trains a Random Forest classifier on `data/synthetic/eligibility_training_data.csv`
and saves it to `app/models/eligibility_model.joblib`.

## Running the full multi-agent pipeline (Phase 4)

Requires Ollama running locally with the model pulled:
```bash
ollama pull llama3
```

Then:
```bash
python -m app.agents.orchestrator data/synthetic/applicant_1
```

Runs extraction -> validation -> eligibility -> decision end-to-end, with the
decision agent using the local LLM to generate reasoning and an enablement
recommendation. Falls back to rule-based reasoning if Ollama isn't reachable.
Note: local LLM calls can take 30-90+ seconds depending on hardware.

## Running the API + chat interface (Phase 5)

**1. Start the backend API** (in one terminal):
```bash
uvicorn app.api.main:app --reload
```
API available at http://localhost:8000 — docs at http://localhost:8000/docs

**2. Start the frontend** (in a second terminal, same venv activated):
```bash
streamlit run frontend/app.py
```
Opens a browser chat interface at http://localhost:8501 where you can upload
the four documents and get a live eligibility assessment.

