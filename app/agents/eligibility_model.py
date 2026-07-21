"""
Phase 3 — Eligibility Assessment.
Trains a classification model on the synthetic eligibility_training_data.csv
and saves it for use by the decision agent.
"""
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score

MODEL_PATH = "app/models/eligibility_model.joblib"
ENCODER_PATH = "app/models/employment_encoder.joblib"

FEATURE_COLUMNS = [
    "monthly_income_aed",
    "family_size",
    "years_employment",
    "total_liabilities_aed",
    "total_assets_aed",
    "credit_score",
    "income_per_capita",
    "debt_to_asset_ratio",
    "employment_status_encoded",
]


def train_model(csv_path: str = "data/synthetic/eligibility_training_data.csv"):
    df = pd.read_csv(csv_path)

    encoder = LabelEncoder()
    df["employment_status_encoded"] = encoder.fit_transform(df["employment_status"])

    X = df[FEATURE_COLUMNS]
    y = df["eligibility_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print("Accuracy:", accuracy_score(y_test, preds))
    print(classification_report(y_test, preds))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(encoder, ENCODER_PATH)
    print(f"Model saved to {MODEL_PATH}")

    return model, encoder


def predict_eligibility(applicant_features: dict, model=None, encoder=None) -> dict:
    """
    applicant_features must contain: monthly_income_aed, family_size,
    years_employment, total_liabilities_aed, total_assets_aed, credit_score,
    employment_status
    """
    if model is None:
        model = joblib.load(MODEL_PATH)
    if encoder is None:
        encoder = joblib.load(ENCODER_PATH)

    income = applicant_features["monthly_income_aed"]
    family_size = max(applicant_features["family_size"], 1)
    liabilities = applicant_features["total_liabilities_aed"]
    assets = applicant_features["total_assets_aed"]

    income_per_capita = income / family_size
    debt_to_asset_ratio = liabilities / (assets + 1)

    try:
        employment_encoded = encoder.transform([applicant_features["employment_status"]])[0]
    except ValueError:
        employment_encoded = 0  # unseen category fallback

    row = pd.DataFrame([{
        "monthly_income_aed": income,
        "family_size": family_size,
        "years_employment": applicant_features.get("years_employment", 0),
        "total_liabilities_aed": liabilities,
        "total_assets_aed": assets,
        "credit_score": applicant_features.get("credit_score", 600),
        "income_per_capita": income_per_capita,
        "debt_to_asset_ratio": debt_to_asset_ratio,
        "employment_status_encoded": employment_encoded,
    }])[FEATURE_COLUMNS]

    prediction = model.predict(row)[0]
    probability = model.predict_proba(row)[0]
    confidence = max(probability)

    return {
        "decision": prediction,
        "confidence": round(float(confidence), 3),
        "income_per_capita": round(income_per_capita, 2),
        "debt_to_asset_ratio": round(debt_to_asset_ratio, 2),
    }


if __name__ == "__main__":
    train_model()

    # quick sanity check prediction
    example = {
        "monthly_income_aed": 3000,
        "family_size": 4,
        "years_employment": 2,
        "total_liabilities_aed": 20000,
        "total_assets_aed": 5000,
        "credit_score": 550,
        "employment_status": "Part-time",
    }
    result = predict_eligibility(example)
    print("\nExample prediction:", result)
