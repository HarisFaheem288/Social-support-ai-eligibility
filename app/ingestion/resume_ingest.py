"""
Extracts employment history and family size from the applicant's resume PDF.
This closes a gap from the original requirements: employment history and
family size were previously hardcoded defaults in the eligibility pipeline.
"""
import re
from app.ingestion.pdf_ingest import extract_pdf_text


def parse_resume(filepath: str) -> dict:
    """
    Parses a resume PDF and returns structured fields:
    employment_status, years_employment, family_size.
    """
    text = extract_pdf_text(filepath)

    result = {
        "employment_status": None,
        "years_employment": None,
        "family_size": None,
    }

    status_match = re.search(r"Employment Status:?\s*([A-Za-z\-]+)", text)
    if status_match:
        result["employment_status"] = status_match.group(1).strip()

    years_match = re.search(r"Years of Employment:?\s*(\d+)", text)
    if years_match:
        result["years_employment"] = int(years_match.group(1))

    family_match = re.search(r"Family Size.*?:?\s*(\d+)", text)
    if family_match:
        result["family_size"] = int(family_match.group(1))

    return result


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python resume_ingest.py <resume.pdf>")
        sys.exit(1)
    print(json.dumps(parse_resume(sys.argv[1]), indent=2, default=str))
