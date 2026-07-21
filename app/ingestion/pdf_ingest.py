"""
Extracts text and tables from PDF documents (bank statements, credit reports).
Uses pdfplumber for layout-aware extraction.
"""
import pdfplumber
import re


def extract_pdf_text(filepath: str) -> str:
    """Extract raw text from all pages of a PDF."""
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    return text


def extract_pdf_tables(filepath: str) -> list:
    """Extract all tables from a PDF as list of list-of-rows."""
    all_tables = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            all_tables.extend(tables)
    return all_tables


def parse_bank_statement(filepath: str) -> dict:
    """
    Parses a bank statement PDF and returns structured fields:
    account holder, opening/closing balance, and transaction list.
    """
    text = extract_pdf_text(filepath)
    tables = extract_pdf_tables(filepath)

    result = {
        "account_holder": None,
        "opening_balance": None,
        "closing_balance": None,
        "transactions": [],
    }

    holder_match = re.search(r"Account Holder:\s*(.+)", text)
    if holder_match:
        result["account_holder"] = holder_match.group(1).strip()

    opening_match = re.search(r"Opening Balance:\s*([\d,]+\.\d{2})", text)
    if opening_match:
        result["opening_balance"] = float(opening_match.group(1).replace(",", ""))

    closing_match = re.search(r"Closing Balance:\s*([\d,]+\.\d{2})", text)
    if closing_match:
        result["closing_balance"] = float(closing_match.group(1).replace(",", ""))

    # Transaction table is usually the second table (first is the info block)
    for table in tables:
        if table and table[0] and "Date" in str(table[0]):
            headers = table[0]
            for row in table[1:]:
                result["transactions"].append(dict(zip(headers, row)))

    return result


def parse_credit_report(filepath: str) -> dict:
    """
    Parses a credit report PDF and returns structured fields:
    name, Emirates ID, credit score, liabilities.
    """
    text = extract_pdf_text(filepath)
    tables = extract_pdf_tables(filepath)

    result = {
        "full_name": None,
        "emirates_id": None,
        "credit_score": None,
        "liabilities": [],
    }

    name_match = re.search(r"Full Name:\s*(.+)", text)
    if name_match:
        result["full_name"] = name_match.group(1).strip()

    eid_match = re.search(r"Emirates ID:\s*([\d\-]+)", text)
    if eid_match:
        result["emirates_id"] = eid_match.group(1).strip()

    score_match = re.search(r"Credit Score:\s*(\d+)", text)
    if score_match:
        result["credit_score"] = int(score_match.group(1))

    for table in tables:
        if table and table[0] and "Liability Type" in str(table[0]):
            headers = table[0]
            for row in table[1:]:
                result["liabilities"].append(dict(zip(headers, row)))

    return result


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_ingest.py <bank_statement.pdf | credit_report.pdf>")
        sys.exit(1)

    path = sys.argv[1]
    if "bank" in path.lower():
        print(json.dumps(parse_bank_statement(path), indent=2, default=str))
    else:
        print(json.dumps(parse_credit_report(path), indent=2, default=str))
