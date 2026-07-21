"""
Full ingestion pipeline for a single applicant's document set.
Reads bank statement, credit report, Emirates ID, and assets/liabilities Excel,
combines them into one structured applicant record, and stores:
  - structured fields -> PostgreSQL
  - raw extracted content -> MongoDB
"""
import json
from datetime import datetime

from app.ingestion.pdf_ingest import parse_bank_statement, parse_credit_report
from app.ingestion.excel_ingest import parse_assets_liabilities
from app.ingestion.id_ingest import parse_emirates_id
from app.db.connections import get_postgres_connection, get_mongo_db


def ingest_applicant(doc_folder: str) -> dict:
    """
    doc_folder must contain: bank_statement.pdf, credit_report.pdf,
    emirates_id_mock.png, assets_liabilities.xlsx
    """
    bank_data = parse_bank_statement(f"{doc_folder}/bank_statement.pdf")
    credit_data = parse_credit_report(f"{doc_folder}/credit_report.pdf")
    id_data = parse_emirates_id(f"{doc_folder}/emirates_id_mock.png")
    assets_data = parse_assets_liabilities(f"{doc_folder}/assets_liabilities.xlsx")

    # Derive monthly income from bank statement credits (simple heuristic for prototype)
    monthly_income = 0.0
    for tx in bank_data.get("transactions", []):
        credit = tx.get("Credit (AED)")
        if credit and str(credit).strip():
            try:
                monthly_income += float(str(credit).replace(",", ""))
            except ValueError:
                pass

    combined = {
        "full_name": credit_data.get("full_name") or bank_data.get("account_holder") or id_data.get("name"),
        "emirates_id": credit_data.get("emirates_id") or id_data.get("id_number"),
        "date_of_birth": id_data.get("date_of_birth"),
        "nationality": id_data.get("nationality"),
        "monthly_income_aed": monthly_income,
        "credit_score": credit_data.get("credit_score"),
        "total_assets_aed": assets_data.get("total_assets_aed"),
        "total_liabilities_aed": assets_data.get("total_liabilities_aed"),
        "ingested_at": datetime.utcnow().isoformat(),
        "raw": {
            "bank_statement": bank_data,
            "credit_report": credit_data,
            "emirates_id": id_data,
            "assets_liabilities": assets_data,
        },
    }
    return combined


def store_applicant(record: dict):
    """Stores structured fields in Postgres, full raw record in MongoDB."""
    # --- PostgreSQL: structured fields ---
    conn = get_postgres_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO applicants (full_name, emirates_id, date_of_birth, nationality)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (emirates_id) DO UPDATE SET full_name = EXCLUDED.full_name
        RETURNING applicant_id
        """,
        (
            record["full_name"],
            record["emirates_id"],
            None,  # date parsing skipped for prototype simplicity; parse record["date_of_birth"] if needed
            record["nationality"],
        ),
    )
    applicant_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO financial_profile
            (applicant_id, monthly_income_aed, total_assets_aed, total_liabilities_aed, credit_score, source_document)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            applicant_id,
            record["monthly_income_aed"],
            record["total_assets_aed"],
            record["total_liabilities_aed"],
            record["credit_score"],
            "ingestion_pipeline",
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    # --- MongoDB: raw extracted content ---
    mongo_db = get_mongo_db()
    mongo_db.applicant_raw_documents.insert_one({
        "emirates_id": record["emirates_id"],
        "full_name": record["full_name"],
        "raw": record["raw"],
        "ingested_at": record["ingested_at"],
    })

    return applicant_id


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <path_to_applicant_folder>")
        sys.exit(1)

    folder = sys.argv[1]
    record = ingest_applicant(folder)
    print(json.dumps(record, indent=2, default=str))

    applicant_id = store_applicant(record)
    print(f"\nStored applicant_id: {applicant_id}")
