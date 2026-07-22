"""
Phase 5 — FastAPI backend.
Exposes the full ingestion -> validation -> eligibility -> decision pipeline
as an HTTP API that the Streamlit frontend (or any client) can call.
"""
import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.orchestrator import run_pipeline

app = FastAPI(title="Social Support AI — Eligibility Assessment API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # fine for local prototype; restrict in real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


class AssessmentResponse(BaseModel):
    applicant_id: int
    full_name: str
    monthly_income_aed: float
    total_assets_aed: float
    total_liabilities_aed: float
    credit_score: int | None
    employment_status: str | None
    years_employment: int | None
    family_size: int | None
    validation_flags: list
    orchestrator_notes: str
    decision: str
    confidence: float
    reasoning: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/assess", response_model=AssessmentResponse)
async def assess_applicant(
    bank_statement: UploadFile = File(...),
    credit_report: UploadFile = File(...),
    emirates_id: UploadFile = File(...),
    assets_liabilities: UploadFile = File(...),
    resume: UploadFile | None = File(None),
):
    """
    Accepts the four required documents plus an optional resume, runs the
    full pipeline, and returns the eligibility decision with reasoning.
    Resume is optional: if omitted, employment history and family size
    fall back to conservative defaults (see orchestrator_notes in the
    response for whether this happened).
    """
    tmp_dir = tempfile.mkdtemp(prefix="applicant_")
    try:
        file_map = {
            "bank_statement.pdf": bank_statement,
            "credit_report.pdf": credit_report,
            "emirates_id_mock.png": emirates_id,
            "assets_liabilities.xlsx": assets_liabilities,
        }
        if resume is not None:
            file_map["resume.pdf"] = resume

        for filename, upload in file_map.items():
            dest_path = os.path.join(tmp_dir, filename)
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(upload.file, f)

        result = run_pipeline(tmp_dir)

        return AssessmentResponse(
            applicant_id=result["applicant_id"],
            full_name=result["record"]["full_name"],
            monthly_income_aed=result["record"]["monthly_income_aed"],
            total_assets_aed=result["record"]["total_assets_aed"],
            total_liabilities_aed=result["record"]["total_liabilities_aed"],
            credit_score=result["record"]["credit_score"],
            employment_status=result["record"].get("employment_status"),
            years_employment=result["record"].get("years_employment"),
            family_size=result["record"].get("family_size"),
            validation_flags=result["validation_flags"],
            orchestrator_notes=result["orchestrator_plan"]["notes"],
            decision=result["final_decision"]["decision"],
            confidence=result["final_decision"]["confidence"],
            reasoning=result["final_decision"]["reasoning"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/assess_from_folder")
def assess_from_folder(folder_path: str):
    """
    Convenience endpoint for local testing: pass a server-side folder path
    (e.g. 'data/synthetic/applicant_1') instead of uploading files.
    Not for production use.
    """
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")

    result = run_pipeline(folder_path)
    return {
        "applicant_id": result["applicant_id"],
        "full_name": result["record"]["full_name"],
        "validation_flags": result["validation_flags"],
        "decision": result["final_decision"]["decision"],
        "confidence": result["final_decision"]["confidence"],
        "reasoning": result["final_decision"]["reasoning"],
    }
