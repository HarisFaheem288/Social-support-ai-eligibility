"""
Phase 4 — Multi-Agent Orchestration (LangGraph).

Pipeline: extraction -> validation -> eligibility -> decision

Each node updates a shared state (TypedDict). The decision node uses the
local LLM (via Ollama) to produce a human-readable reasoning summary and an
"enablement" recommendation (training / job matching / counseling), with a
rule-based fallback if Ollama isn't reachable.
"""
from typing import TypedDict, Optional, List, Dict, Any
import json
import requests

from langgraph.graph import StateGraph, END

from app.ingestion.pipeline import ingest_applicant, store_applicant
from app.agents.validation import validate_applicant, store_validation_flags
from app.agents.eligibility_model import predict_eligibility
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.db.connections import get_postgres_connection


class ApplicantState(TypedDict):
    doc_folder: str
    record: Optional[Dict[str, Any]]
    applicant_id: Optional[int]
    validation_flags: Optional[List[Dict[str, Any]]]
    eligibility_result: Optional[Dict[str, Any]]
    final_decision: Optional[Dict[str, Any]]


# --- Nodes ---

def extraction_node(state: ApplicantState) -> ApplicantState:
    record = ingest_applicant(state["doc_folder"])
    applicant_id = store_applicant(record)
    state["record"] = record
    state["applicant_id"] = applicant_id
    return state


def validation_node(state: ApplicantState) -> ApplicantState:
    flags = validate_applicant(state["record"])
    store_validation_flags(state["applicant_id"], flags)
    state["validation_flags"] = flags
    return state


def eligibility_node(state: ApplicantState) -> ApplicantState:
    record = state["record"]
    features = {
        "monthly_income_aed": record.get("monthly_income_aed") or 0,
        "family_size": record.get("family_size") or 3,  # not yet extracted from docs; default assumption
        "years_employment": record.get("years_employment") or 2,
        "total_liabilities_aed": record.get("total_liabilities_aed") or 0,
        "total_assets_aed": record.get("total_assets_aed") or 0,
        "credit_score": record.get("credit_score") or 600,
        "employment_status": record.get("employment_status") or "Employed",
    }
    result = predict_eligibility(features)
    state["eligibility_result"] = result
    return state


def _call_ollama(prompt: str) -> Optional[str]:
    """Try the local LLM. Returns None if unreachable so caller can fall back.
    Timeout is generous (240s) since local LLM inference can be slow when the
    system is also running Docker databases, FastAPI, and Streamlit at once.
    keep_alive keeps the model loaded in memory between calls so it doesn't
    have to reload from disk each time, which is a common cause of slowness."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=240,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[orchestrator] Ollama call failed, using fallback reasoning: {type(e).__name__} - {e}")
        return None


def _rule_based_reasoning(record, flags, eligibility) -> str:
    """Fallback reasoning if the LLM isn't reachable."""
    decision = eligibility["decision"]
    reasons = []
    if eligibility["income_per_capita"] < 2000:
        reasons.append("low income per household member")
    if eligibility["debt_to_asset_ratio"] > 1.5:
        reasons.append("liabilities are high relative to assets")
    if flags:
        reasons.append(f"{len(flags)} data consistency flag(s) raised during validation")
    if not reasons:
        reasons.append("financial profile falls within the approval range")
    return f"{decision} based on: {', '.join(reasons)}."


def decision_node(state: ApplicantState) -> ApplicantState:
    record = state["record"]
    flags = state["validation_flags"]
    eligibility = state["eligibility_result"]

    prompt = f"""You are an eligibility decision assistant for a government social support program.
Applicant: {record.get('full_name')}
Monthly income (AED): {record.get('monthly_income_aed')}
Total assets (AED): {record.get('total_assets_aed')}
Total liabilities (AED): {record.get('total_liabilities_aed')}
Credit score: {record.get('credit_score')}
Model decision: {eligibility['decision']} (confidence {eligibility['confidence']})
Validation flags: {json.dumps(flags)}

In 2-3 sentences, explain the reasoning for this decision in plain language suitable for a caseworker.
Then, on a new line starting with "Enablement recommendation:", suggest ONE relevant support
(e.g. job training, career counseling, job matching, financial literacy program) or write "None needed"
if the applicant is approved for direct financial support only."""

    llm_response = _call_ollama(prompt)

    if llm_response:
        reasoning = llm_response
    else:
        reasoning = _rule_based_reasoning(record, flags, eligibility) + \
            " (Note: generated via rule-based fallback — local LLM was not reachable.)"

    final_decision = {
        "applicant_id": state["applicant_id"],
        "decision": eligibility["decision"],
        "confidence": eligibility["confidence"],
        "reasoning": reasoning,
    }
    state["final_decision"] = final_decision

    # persist to Postgres
    conn = get_postgres_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO eligibility_decisions (applicant_id, decision, confidence, reasoning)
        VALUES (%s, %s, %s, %s)
        """,
        (state["applicant_id"], eligibility["decision"], eligibility["confidence"], reasoning),
    )
    conn.commit()
    cur.close()
    conn.close()

    return state


# --- Graph assembly ---

def build_graph():
    graph = StateGraph(ApplicantState)
    graph.add_node("extraction", extraction_node)
    graph.add_node("validation", validation_node)
    graph.add_node("eligibility", eligibility_node)
    graph.add_node("decision", decision_node)

    graph.set_entry_point("extraction")
    graph.add_edge("extraction", "validation")
    graph.add_edge("validation", "eligibility")
    graph.add_edge("eligibility", "decision")
    graph.add_edge("decision", END)

    return graph.compile()


def run_pipeline(doc_folder: str) -> dict:
    app = build_graph()
    initial_state: ApplicantState = {
        "doc_folder": doc_folder,
        "record": None,
        "applicant_id": None,
        "validation_flags": None,
        "eligibility_result": None,
        "final_decision": None,
    }
    result = app.invoke(initial_state)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m app.agents.orchestrator <path_to_applicant_folder>")
        sys.exit(1)

    result = run_pipeline(sys.argv[1])
    print("\n=== FINAL RESULT ===")
    print(f"Applicant ID: {result['applicant_id']}")
    print(f"Full name: {result['record']['full_name']}")
    print(f"Validation flags: {len(result['validation_flags'])}")
    print(f"Eligibility: {result['eligibility_result']}")
    print(f"\nDecision: {result['final_decision']['decision']} (confidence {result['final_decision']['confidence']})")
    print(f"Reasoning:\n{result['final_decision']['reasoning']}")
