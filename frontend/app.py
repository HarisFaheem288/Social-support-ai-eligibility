"""
Phase 5 — Streamlit frontend (enhanced).
Chat-style interface with custom styling, live progress steps, and a
polished decision summary with metric cards.
"""
import streamlit as st
import requests
import time

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Social Support AI Assistant",
    page_icon="🏛️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------- Custom styling ----------
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .main-header h1 {
        font-size: 2.2rem;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        text-align: center;
        color: #6b7280;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .decision-card {
        border-radius: 16px;
        padding: 1.5rem 1.8rem;
        margin: 1rem 0;
        border: 1px solid rgba(0,0,0,0.08);
    }
    .decision-approved {
        background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
        border-left: 5px solid #16a34a;
    }
    .decision-declined {
        background: linear-gradient(135deg, #fef2f2 0%, #fff5f5 100%);
        border-left: 5px solid #dc2626;
    }
    .decision-soft-decline {
        background: linear-gradient(135deg, #fffbeb 0%, #fffdf5 100%);
        border-left: 5px solid #f59e0b;
    }
    .decision-title {
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }
    .confidence-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font-size: 0.85rem;
        font-weight: 600;
        background: rgba(0,0,0,0.06);
        margin-left: 0.5rem;
    }
    .flag-box {
        background: #fffbeb;
        border-left: 4px solid #f59e0b;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-top: 1rem;
        font-size: 0.9rem;
    }
    .upload-section {
        background: #fafafa;
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        border: 1px solid rgba(0,0,0,0.06);
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.3rem;
        white-space: normal;
        overflow-wrap: break-word;
    }
    div[data-testid="stMetric"] {
        background: #f8fafc;
        border-radius: 10px;
        padding: 0.7rem 0.6rem;
        border: 1px solid rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ---------- Header ----------
st.markdown("""
<div class="main-header">
    <h1>🏛️ Social Support Eligibility Assistant</h1>
</div>
<div class="subtitle">AI-powered document review and instant eligibility assessment</div>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("ℹ️ How it works")
    st.markdown("""
    1. **Upload** your four required documents
    2. Our AI **extracts and validates** your information
    3. An **eligibility model** assesses your case
    4. A **local AI assistant** explains the decision in plain language

    ---
    **Required documents:**
    - 🏦 Bank Statement (PDF)
    - 📊 Credit Report (PDF)
    - 🪪 Emirates ID (image)
    - 📈 Assets/Liabilities (Excel)

    ---
    ⚠️ *Prototype for demonstration purposes only. Not connected to a real government database.*
    """)

    if st.button("🔄 Start New Application", use_container_width=True):
        st.session_state.messages = []
        st.session_state.result = None
        st.rerun()

# ---------- Session state ----------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I can help assess your eligibility for social support. "
                                          "Please upload your four required documents below to get started."}
    ]
if "result" not in st.session_state:
    st.session_state.result = None

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------- Upload section ----------
st.markdown('<div class="upload-section">', unsafe_allow_html=True)
st.markdown("##### 📎 Upload your documents")
col1, col2 = st.columns(2)
with col1:
    bank_statement = st.file_uploader("🏦 Bank Statement (PDF)", type=["pdf"])
    emirates_id = st.file_uploader("🪪 Emirates ID (image)", type=["png", "jpg", "jpeg"])
    resume = st.file_uploader("📄 Resume (PDF) — optional", type=["pdf"])
with col2:
    credit_report = st.file_uploader("📊 Credit Report (PDF)", type=["pdf"])
    assets_liabilities = st.file_uploader("📈 Assets/Liabilities (Excel)", type=["xlsx"])

st.caption("💡 Resume is optional — if omitted, employment history and family size use conservative defaults instead of your actual data.")

all_uploaded = all([bank_statement, credit_report, emirates_id, assets_liabilities])
uploaded_count = sum(bool(f) for f in [bank_statement, credit_report, emirates_id, assets_liabilities])
st.progress(uploaded_count / 4, text=f"{uploaded_count} of 4 documents uploaded")

submit = st.button("🚀 Submit Application", type="primary", use_container_width=True, disabled=not all_uploaded)
st.markdown('</div>', unsafe_allow_html=True)

# ---------- Submission flow ----------
if submit:
    st.session_state.messages.append({"role": "user", "content": "I've submitted my documents for assessment."})
    with st.chat_message("user"):
        st.markdown("I've submitted my documents for assessment.")

    with st.chat_message("assistant"):
        status_box = st.status("Starting assessment...", expanded=True)
        try:
            status_box.write("📄 Extracting data from your documents...")
            time.sleep(0.4)
            status_box.write("🔎 Validating document consistency...")
            time.sleep(0.4)
            status_box.write("📊 Running eligibility model...")
            time.sleep(0.4)
            status_box.write("🧠 Generating explanation with local AI (this can take up to a minute)...")

            files = {
                "bank_statement": (bank_statement.name, bank_statement.getvalue(), "application/pdf"),
                "credit_report": (credit_report.name, credit_report.getvalue(), "application/pdf"),
                "emirates_id": (emirates_id.name, emirates_id.getvalue(), "image/png"),
                "assets_liabilities": (assets_liabilities.name, assets_liabilities.getvalue(),
                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            }
            if resume is not None:
                files["resume"] = (resume.name, resume.getvalue(), "application/pdf")
            resp = requests.post(f"{API_URL}/assess", files=files, timeout=280)
            resp.raise_for_status()
            result = resp.json()
            st.session_state.result = result

            status_box.update(label="✅ Assessment complete", state="complete", expanded=False)

        except requests.exceptions.ConnectionError:
            status_box.update(label="⚠️ Connection failed", state="error")
            st.error("Could not connect to the backend API. Make sure it's running: `uvicorn app.api.main:app --reload`")
            st.session_state.result = None
        except Exception as e:
            status_box.update(label="⚠️ Error", state="error")
            st.error(f"Something went wrong: {e}")
            st.session_state.result = None

# ---------- Result display ----------
if st.session_state.result:
    result = st.session_state.result
    decision = result["decision"]

    if decision == "Approved":
        card_class, emoji = "decision-approved", "✅"
    elif decision == "Soft Decline":
        card_class, emoji = "decision-soft-decline", "⚠️"
    else:
        card_class, emoji = "decision-declined", "❌"

    st.markdown(f"""
    <div class="decision-card {card_class}">
        <div class="decision-title">{emoji} {decision}
            <span class="confidence-badge">{result['confidence']*100:.0f}% confidence</span>
        </div>
        <div style="color:#374151;">Applicant: <strong>{result['full_name']}</strong></div>
    </div>
    """, unsafe_allow_html=True)

    if decision == "Soft Decline":
        st.warning("This case is borderline and has been flagged for human caseworker review rather than an automatic decision.")

    def fmt_aed(value):
        if value >= 1_000_000:
            return f"AED {value/1_000_000:.2f}M"
        return f"AED {value:,.0f}"

    row1_col1, row1_col2 = st.columns(2)
    row1_col1.metric("Monthly Income", fmt_aed(result['monthly_income_aed']))
    row1_col2.metric("Total Assets", fmt_aed(result['total_assets_aed']))

    row2_col1, row2_col2 = st.columns(2)
    row2_col1.metric("Total Liabilities", fmt_aed(result['total_liabilities_aed']))
    row2_col2.metric("Credit Score", f"{result['credit_score']}")

    row3_col1, row3_col2, row3_col3 = st.columns(3)
    row3_col1.metric("Employment Status", result.get("employment_status") or "Unknown")
    row3_col2.metric("Years Employed", result.get("years_employment") if result.get("years_employment") is not None else "Unknown")
    row3_col3.metric("Family Size", result.get("family_size") if result.get("family_size") is not None else "Unknown")

    st.markdown("##### 🧠 AI Reasoning")
    st.info(result["reasoning"])

    if result["validation_flags"]:
        flags_html = "".join(f"<li>{f['description']}</li>" for f in result["validation_flags"])
        st.markdown(f"""
        <div class="flag-box">
            <strong>⚠️ Data consistency notes:</strong>
            <ul>{flags_html}</ul>
        </div>
        """, unsafe_allow_html=True)

    response_summary = f"**{emoji} {result['decision']}** ({result['confidence']*100:.0f}% confidence) — {result['reasoning']}"
    if not any(response_summary == m["content"] for m in st.session_state.messages):
        st.session_state.messages.append({"role": "assistant", "content": response_summary})

st.divider()
st.caption("Prototype for demonstration purposes. Not connected to a real government database.")
