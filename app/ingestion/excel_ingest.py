"""
Extracts structured data from the assets/liabilities Excel file.
"""
import pandas as pd


def parse_assets_liabilities(filepath: str) -> dict:
    """
    Reads the two-sheet Excel file (Assets, Liabilities) and returns
    structured totals plus itemized lists.
    """
    assets_df = pd.read_excel(filepath, sheet_name="Assets")
    liabilities_df = pd.read_excel(filepath, sheet_name="Liabilities")

    total_assets = float(assets_df["Estimated Value (AED)"].sum())
    total_liabilities = float(liabilities_df["Outstanding Amount (AED)"].sum())
    total_monthly_liability_payments = float(liabilities_df["Monthly Payment (AED)"].sum())

    return {
        "assets": assets_df.to_dict(orient="records"),
        "liabilities": liabilities_df.to_dict(orient="records"),
        "total_assets_aed": total_assets,
        "total_liabilities_aed": total_liabilities,
        "total_monthly_liability_payments_aed": total_monthly_liability_payments,
    }


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python excel_ingest.py <assets_liabilities.xlsx>")
        sys.exit(1)
    print(json.dumps(parse_assets_liabilities(sys.argv[1]), indent=2, default=str))
