"""
Extracts fields from the Emirates ID image using OCR (pytesseract).
Requires Tesseract OCR engine installed separately (not just the Python package).
"""
import pytesseract
from PIL import Image
import re


def extract_id_text(filepath: str) -> str:
    """Run OCR on the ID image and return raw text."""
    image = Image.open(filepath)
    return pytesseract.image_to_string(image)


def parse_emirates_id(filepath: str) -> dict:
    """
    Parses an Emirates ID image and returns structured fields:
    ID number, name, nationality, date of birth.
    """
    text = extract_id_text(filepath)

    result = {
        "id_number": None,
        "name": None,
        "nationality": None,
        "date_of_birth": None,
    }

    id_match = re.search(r"ID Number:?\s*([\d\-]+)", text)
    if id_match:
        result["id_number"] = id_match.group(1).strip()

    name_match = re.search(r"Name:?\s*([A-Za-z\s]+?)(?:\n|$)", text)
    if name_match:
        result["name"] = name_match.group(1).strip()

    nat_match = re.search(r"Nationality:?\s*([A-Za-z\s]+?)(?:\n|$)", text)
    if nat_match:
        result["nationality"] = nat_match.group(1).strip()

    dob_match = re.search(r"Date of Birth:?\s*([\d/]+)", text)
    if dob_match:
        result["date_of_birth"] = dob_match.group(1).strip()

    result["_raw_ocr_text"] = text
    return result


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python id_ingest.py <emirates_id_mock.png>")
        sys.exit(1)
    print(json.dumps(parse_emirates_id(sys.argv[1]), indent=2, default=str))
