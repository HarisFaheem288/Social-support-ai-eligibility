"""
Phase 2 — Validation.
Cross-checks consistency between the different documents ingested for one
applicant, and flags discrepancies (e.g. mismatched name, missing fields,
implausible values).
"""
from app.db.connections import get_postgres_connection


def validate_applicant(record: dict) -> list:
    """
    Takes the combined record produced by app.ingestion.pipeline.ingest_applicant()
    and returns a list of validation flags (empty list = no issues found).
    Each flag: {type, description, severity}
    """
    flags = []
    raw = record.get("raw", {})

    bank_holder = (raw.get("bank_statement", {}).get("account_holder") or "").strip().lower()
    credit_name = (raw.get("credit_report", {}).get("full_name") or "").strip().lower()
    id_name = (raw.get("emirates_id", {}).get("name") or "").strip().lower()

    # 1. Name consistency across documents
    names = {n for n in [bank_holder, credit_name, id_name] if n}
    if len(names) > 1:
        flags.append({
            "type": "name_mismatch",
            "description": f"Name differs across documents: {names}",
            "severity": "high",
        })

    # 2. Emirates ID present and consistent
    credit_eid = raw.get("credit_report", {}).get("emirates_id")
    id_eid = raw.get("emirates_id", {}).get("id_number")
    if credit_eid and id_eid and credit_eid.strip() != id_eid.strip():
        flags.append({
            "type": "id_mismatch",
            "description": f"Emirates ID differs between credit report ({credit_eid}) and ID card ({id_eid})",
            "severity": "high",
        })
    if not credit_eid and not id_eid:
        flags.append({
            "type": "missing_id",
            "description": "No Emirates ID found in either credit report or ID card",
            "severity": "high",
        })

    # 3. Missing critical fields
    if record.get("monthly_income_aed") is None or record.get("monthly_income_aed") == 0:
        flags.append({
            "type": "missing_income",
            "description": "No income detected from bank statement credits",
            "severity": "medium",
        })

    if record.get("credit_score") is None:
        flags.append({
            "type": "missing_credit_score",
            "description": "Credit score not found in credit report",
            "severity": "medium",
        })

    # 4. Plausibility checks
    income = record.get("monthly_income_aed") or 0
    liabilities = record.get("total_liabilities_aed") or 0
    if income > 0 and (liabilities / max(income, 1)) > 500:
        flags.append({
            "type": "implausible_debt_ratio",
            "description": "Liabilities are extremely high relative to monthly income — verify manually",
            "severity": "medium",
        })

    credit_score = record.get("credit_score")
    if credit_score is not None and not (300 <= credit_score <= 900):
        flags.append({
            "type": "invalid_credit_score",
            "description": f"Credit score {credit_score} outside expected 300–900 range",
            "severity": "high",
        })

    return flags


def store_validation_flags(applicant_id: int, flags: list):
    if not flags:
        return
    conn = get_postgres_connection()
    cur = conn.cursor()
    for f in flags:
        cur.execute(
            """
            INSERT INTO validation_flags (applicant_id, flag_type, description, severity)
            VALUES (%s, %s, %s, %s)
            """,
            (applicant_id, f["type"], f["description"], f["severity"]),
        )
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    import sys
    import json
    from app.ingestion.pipeline import ingest_applicant, store_applicant

    if len(sys.argv) < 2:
        print("Usage: python -m app.agents.validation <path_to_applicant_folder>")
        sys.exit(1)

    folder = sys.argv[1]
    record = ingest_applicant(folder)
    applicant_id = store_applicant(record)
    flags = validate_applicant(record)
    store_validation_flags(applicant_id, flags)

    print(f"Applicant ID: {applicant_id}")
    print(f"Validation flags ({len(flags)}):")
    print(json.dumps(flags, indent=2))
