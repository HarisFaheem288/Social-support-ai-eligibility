# Social Support AI — Eligibility Assessment Prototype

An AI-powered prototype that automates intake, validation, and eligibility
assessment for government social/financial support applications.

## Architecture

- **Ingestion**: extracts structured data from bank statements, credit reports,
  Emirates ID, and assets/liabilities spreadsheets (`app/ingestion/`)
- **Storage**: PostgreSQL (structured fields), MongoDB (raw document content),
  Qdrant (semantic embeddings), Neo4j (relationship graph — household/family links)
- **Agents**: multi-agent pipeline (extraction → validation → eligibility →
  decision) built with LangGraph (`app/agents/`)
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
- `applicant_1/` — mid-income, borderline case
- `applicant_2/` — low-income, clearly eligible case
- `applicant_3/` — high-income, clearly ineligible case

`data/synthetic/eligibility_training_data.csv` — 300-row synthetic dataset
for training the eligibility classification model.

## Running the ingestion pipeline (Phase 1)

```bash
python -m app.ingestion.pipeline data/synthetic/applicant_1
```

This extracts, combines, and stores one applicant's full document set into
PostgreSQL + MongoDB, printing the structured record to console.

## Next phases (to be built)

- Phase 2: Validation agent (cross-document consistency checks)
- Phase 3: Eligibility model (scikit-learn classifier on training CSV)
- Phase 4: Multi-agent orchestration (LangGraph)
- Phase 5: FastAPI + Streamlit chat interface
- Phase 6: Documentation, architecture diagram, walkthrough video
