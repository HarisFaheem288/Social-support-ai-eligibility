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
import re
import requests

from langgraph.graph import StateGraph, END

from app.ingestion.pipeline import ingest_applicant, store_applicant
from app.agents.validation import validate_applicant, store_validation_flags
from app.agents.eligibility_model import predict_eligibility
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.db.connections import get_postgres_connection
from app.observability.tracing import trace_step

# Confidence below this threshold on a "Declined" model result is downgraded
# to "Soft Decline" rather than a hard rejection — signals a borderline case
# that may warrant human review or reapplication with more information,
# rather than a definitive no.
SOFT_DECLINE_CONFIDENCE_THRESHOLD = 0.65


class ApplicantState(TypedDict):
    doc_folder: str
    orchestrator_plan: Optional[Dict[str, Any]]
    record: Optional[Dict[str, Any]]
    applicant_id: Optional[int]
    validation_flags: Optional[List[Dict[str, Any]]]
    eligibility_result: Optional[Dict[str, Any]]
    final_decision: Optional[Dict[str, Any]]


# --- Nodes ---

def orchestrator_node(state: ApplicantState) -> ApplicantState:
    """
    Master orchestrator agent. Inspects the applicant's document folder,
    decides which documents are available, and builds an explicit execution
    plan before dispatching to the extraction/validation/eligibility/decision
    sub-agents. This gives the pipeline a distinct planning/reasoning step
    rather than relying purely on the graph's fixed edges.
    """
    import os
    with trace_step("applicant_assessment", "orchestrator_plan", {"doc_folder": state["doc_folder"]}) as t:
        doc_folder = state["doc_folder"]
        required_docs = {
            "bank_statement.pdf": "bank statement",
            "credit_report.pdf": "credit report",
            "emirates_id_mock.png": "Emirates ID",
            "assets_liabilities.xlsx": "assets/liabilities spreadsheet",
        }

        available = []
        missing = []
        for filename, label in required_docs.items():
            path = os.path.join(doc_folder, filename)
            (available if os.path.exists(path) else missing).append(label)

        resume_available = os.path.exists(os.path.join(doc_folder, "resume.pdf"))

        plan = {
            "available_documents": available,
            "missing_required_documents": missing,
            "resume_available": resume_available,
            "can_proceed": len(missing) == 0,
            "notes": (
                "All required documents present, proceeding with full pipeline."
                if not missing else
                f"Missing required document(s): {', '.join(missing)}. Pipeline will likely fail at extraction."
            ),
        }
        if not resume_available:
            plan["notes"] += " Resume not provided — employment history and family size will use fallback defaults."

        print(f"[orchestrator] Plan: {plan['notes']}")
        state["orchestrator_plan"] = plan
        t["output"] = plan
    return state

def extraction_node(state: ApplicantState) -> ApplicantState:
    with trace_step("applicant_assessment", "extraction", {"doc_folder": state["doc_folder"]}) as t:
        record = ingest_applicant(state["doc_folder"])
        applicant_id = store_applicant(record)
        state["record"] = record
        state["applicant_id"] = applicant_id
        t["output"] = {"applicant_id": applicant_id, "full_name": record.get("full_name")}
    return state


def validation_node(state: ApplicantState) -> ApplicantState:
    with trace_step("applicant_assessment", "validation", {"applicant_id": state["applicant_id"]}) as t:
        flags = validate_applicant(state["record"])
        store_validation_flags(state["applicant_id"], flags)
        state["validation_flags"] = flags
        t["output"] = {"flag_count": len(flags), "flags": [f["type"] for f in flags]}
    return state


def eligibility_node(state: ApplicantState) -> ApplicantState:
    with trace_step("applicant_assessment", "eligibility", {"applicant_id": state["applicant_id"]}) as t:
        record = state["record"]

        # Prefer values actually extracted from the resume. Fall back to
        # conservative defaults only if the resume was missing or a field
        # wasn't found in it (e.g. OCR/parsing miss) — and note the fallback
        # so it's traceable rather than silently guessed.
        family_size = record.get("family_size")
        years_employment = record.get("years_employment")
        employment_status = record.get("employment_status")

        if family_size is None:
            family_size = 3
            print("[orchestrator] family_size not found in resume, using default fallback (3)")
        if years_employment is None:
            years_employment = 2
            print("[orchestrator] years_employment not found in resume, using default fallback (2)")
        if employment_status is None:
            employment_status = "Employed"
            print("[orchestrator] employment_status not found in resume, using default fallback (Employed)")

        features = {
            "monthly_income_aed": record.get("monthly_income_aed") or 0,
            "family_size": family_size,
            "years_employment": years_employment,
            "total_liabilities_aed": record.get("total_liabilities_aed") or 0,
            "total_assets_aed": record.get("total_assets_aed") or 0,
            "credit_score": record.get("credit_score") or 600,
            "employment_status": employment_status,
        }
        result = predict_eligibility(features)

        # Soft-decline logic: a "Declined" result with low model confidence
        # is treated as borderline rather than a hard rejection.
        if result["decision"] == "Declined" and result["confidence"] < SOFT_DECLINE_CONFIDENCE_THRESHOLD:
            result["decision"] = "Soft Decline"
            result["soft_decline_reason"] = (
                f"Model confidence ({result['confidence']*100:.0f}%) below the "
                f"{SOFT_DECLINE_CONFIDENCE_THRESHOLD*100:.0f}% threshold for a hard decline — "
                "recommended for human caseworker review rather than automatic rejection."
            )

        state["eligibility_result"] = result
        t["output"] = result
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


def _parse_react_response(raw: str) -> dict:
    """
    Parses the LLM's ReAct-style response into its components.
    Falls back gracefully if the model doesn't follow the format exactly —
    treats the whole response as the final answer in that case.
    """
    sections = {"thought": None, "action": None, "observation": None, "final_answer": None}
    patterns = {
        "thought": r"Thought:\s*(.+?)(?=\nAction:|\nObservation:|\nFinal Answer:|$)",
        "action": r"Action:\s*(.+?)(?=\nObservation:|\nFinal Answer:|$)",
        "observation": r"Observation:\s*(.+?)(?=\nFinal Answer:|$)",
        "final_answer": r"Final Answer:\s*(.+)$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            sections[key] = match.group(1).strip()

    if not sections["final_answer"]:
        # Model didn't follow the ReAct format — use the raw response as-is.
        sections["final_answer"] = raw.strip()

    return sections


def _reasoning_contradicts_data(reasoning: str, record: dict) -> bool:
    """
    Lightweight sanity check to catch LLM hallucinations where the generated
    explanation contradicts the actual applicant data (e.g. calling a high
    income 'low'). Not exhaustive, but catches the most common failure mode
    observed when running smaller models on CPU-only inference.
    """
    income = record.get("monthly_income_aed") or 0
    assets = record.get("total_assets_aed") or 0
    reasoning_lower = reasoning.lower()

    # High income (>15k/month) but reasoning claims it's low
    if income > 15000 and re.search(r"low income|struggling|insufficient income|can't make ends meet|cannot make ends meet", reasoning_lower):
        return True
    # High assets (>500k) but reasoning claims financial hardship without qualification
    if assets > 500000 and re.search(r"struggling to make ends meet|financial hardship|lacks? (sufficient )?assets", reasoning_lower):
        return True
    # Very low income (<3k/month) but reasoning claims it's high/sufficient
    if 0 < income < 3000 and re.search(r"high income|sufficient income|substantial income", reasoning_lower):
        return True

    return False


def decision_node(state: ApplicantState) -> ApplicantState:
    with trace_step("applicant_assessment", "decision", {"applicant_id": state["applicant_id"]}) as t:
        record = state["record"]
        flags = state["validation_flags"]
        eligibility = state["eligibility_result"]

        # ReAct-style prompt: the model is asked to explicitly reason (Thought),
        # identify what it's checking (Action), state what it finds (Observation),
        # and only then commit to a Final Answer. This is a lightweight,
        # single-pass adaptation of the ReAct pattern (Yao et al., 2022) —
        # not a full multi-turn tool-calling agent loop, but it does force
        # explicit intermediate reasoning rather than a direct answer, and
        # the intermediate steps are captured and stored for auditability.
        prompt = f"""You are an eligibility decision assistant for a government social support program.
You MUST base your reasoning strictly on the exact numbers provided below. Do not guess, generalize, or invent details not present in the data. If income is high, say it is high. If assets are high, say they are high. Do not contradict the numbers given.

Use this exact format:

Thought: <reason step by step about the applicant's financial situation, referencing the exact figures given>
Action: <name what factor you are checking, e.g. "checking income relative to family size">
Observation: <state what you find when checking that factor, using the exact numbers>
Final Answer: <2-3 sentence plain-language explanation for a caseworker that accurately reflects the numbers above, then on a new line write "Enablement recommendation:" followed by ONE relevant support (job training, career counseling, job matching, financial literacy program) or "None needed">

Applicant: {record.get('full_name')}
Monthly income (AED): {record.get('monthly_income_aed')}
Total assets (AED): {record.get('total_assets_aed')}
Total liabilities (AED): {record.get('total_liabilities_aed')}
Credit score: {record.get('credit_score')}
Employment status: {record.get('employment_status') or 'Unknown'}
Years employed: {record.get('years_employment') if record.get('years_employment') is not None else 'Unknown'}
Family size: {record.get('family_size') if record.get('family_size') is not None else 'Unknown'}
Income per family member (AED): {round((record.get('monthly_income_aed') or 0) / max(record.get('family_size') or 1, 1), 2)}
Model decision: {eligibility['decision']} (confidence {eligibility['confidence']})
Validation flags: {json.dumps(flags)}"""

        llm_response = _call_ollama(prompt)

        if llm_response:
            parsed = _parse_react_response(llm_response)
            reasoning = parsed["final_answer"]
            reasoning_trace = parsed

            if _reasoning_contradicts_data(reasoning, record):
                print("[orchestrator] LLM reasoning contradicted applicant data (likely hallucination) — using rule-based reasoning instead")
                reasoning = _rule_based_reasoning(record, flags, eligibility) + \
                    " (Note: LLM-generated explanation was discarded because it contradicted the applicant's actual figures; rule-based reasoning used instead.)"
                reasoning_trace["discarded_llm_reasoning"] = parsed["final_answer"]
        else:
            reasoning = _rule_based_reasoning(record, flags, eligibility) + \
                " (Note: generated via rule-based fallback — local LLM was not reachable.)"
            reasoning_trace = {"thought": None, "action": None, "observation": None, "final_answer": reasoning}

        final_decision = {
            "applicant_id": state["applicant_id"],
            "decision": eligibility["decision"],
            "confidence": eligibility["confidence"],
            "reasoning": reasoning,
            "reasoning_trace": reasoning_trace,
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

        t["output"] = {"decision": eligibility["decision"], "used_llm": llm_response is not None}
    return state


# --- Graph assembly ---

def build_graph():
    graph = StateGraph(ApplicantState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("validation", validation_node)
    graph.add_node("eligibility", eligibility_node)
    graph.add_node("decision", decision_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "extraction")
    graph.add_edge("extraction", "validation")
    graph.add_edge("validation", "eligibility")
    graph.add_edge("eligibility", "decision")
    graph.add_edge("decision", END)

    return graph.compile()


def run_pipeline(doc_folder: str) -> dict:
    app = build_graph()
    initial_state: ApplicantState = {
        "doc_folder": doc_folder,
        "orchestrator_plan": None,
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
    print("\n=== ORCHESTRATOR PLAN ===")
    print(result["orchestrator_plan"]["notes"])
    print("\n=== FINAL RESULT ===")
    print(f"Applicant ID: {result['applicant_id']}")
    print(f"Full name: {result['record']['full_name']}")
    print(f"Validation flags: {len(result['validation_flags'])}")
    print(f"Eligibility: {result['eligibility_result']}")
    print(f"\nDecision: {result['final_decision']['decision']} (confidence {result['final_decision']['confidence']})")
    print(f"Reasoning:\n{result['final_decision']['reasoning']}")
