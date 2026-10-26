import os
import sqlite3

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai

load_dotenv()

DB_PATH = "pcards.db"

st.set_page_config(page_title="P-Card Forensic Audit Tool", layout="wide")
st.title("💳 P-Card Forensic Audit Assistant")


# ---------------------------------------------------------------------------
# Database helpers (the database is opened read-only so no query can change it)
# ---------------------------------------------------------------------------

def get_connection():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def run_query(sql, params=()):
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


@st.cache_data
def get_db_schema():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT sql FROM sqlite_master WHERE type='table';").fetchall()
    finally:
        conn.close()
    return "\n".join(r[0] for r in rows if r[0])


@st.cache_data
def get_years():
    df = run_query("SELECT DISTINCT Year FROM pcards ORDER BY Year DESC")
    return df["Year"].tolist()


RESULT_COLUMNS = """
    TransactionDate, PostedDate, FullName, AgencyName, Vendor, Description,
    Amount, MCC, ID AS TransactionID
"""


def search_transactions(field, keyword, year):
    """Search the Description or Vendor field for a keyword (case-insensitive)."""
    if field not in ("Description", "Vendor"):
        raise ValueError("field must be Description or Vendor")
    sql = f"SELECT {RESULT_COLUMNS} FROM pcards WHERE {field} LIKE ?"
    params = [f"%{keyword.strip()}%"]
    if year != "All years":
        sql += " AND Year = ?"
        params.append(int(year))
    sql += " ORDER BY Amount DESC"
    return run_query(sql, params)


# Suggested keywords for each prohibited category in OSU's P-card procedure.
PROHIBITED_CATEGORIES = {
    "Alcohol": {"Description": "alcohol, wine, beer", "Vendor": "bottle shop, liquor, wine",
                "Watch out": "'wine' also matches 'swine' (livestock registries)"},
    "Cash, cash advances, ATM": {"Description": "cash advance, atm", "Vendor": "cash, atm",
                                 "Watch out": "'cash' mostly finds university cashier offices"},
    "Decorations": {"Description": "decoration, balloon, party", "Vendor": "party city, hobby lobby",
                    "Watch out": "craft stores also sell teaching supplies"},
    "Donations and sponsorships": {"Description": "donation, sponsor", "Vendor": "foundation, fund",
                                   "Watch out": "foundations may be legitimate registration fees"},
    "Gasoline": {"Description": "unleaded, gasoline", "Vendor": "oncue, burk oil, short stop, shell",
                 "Watch out": "'fuel' in descriptions often means fuel filters or parts"},
    "Gifts, gift cards, gift certificates": {"Description": "gift card, gift cert", "Vendor": "gift",
                                             "Watch out": "gift shops can sell normal supplies"},
    "Insurance": {"Description": "insurance", "Vendor": "insurance", "Watch out": ""},
    "Late fees": {"Description": "late fee, late charge, penalty", "Vendor": "late",
                  "Watch out": "'late' also matches 'chocolate', 'plate', 'articulate'"},
    "Mail and postage": {"Description": "postage, stamps", "Vendor": "usps, post office",
                         "Watch out": "'usps' also matches 'Marriott USPS Conference' hotel charges"},
    "Moving expenses": {"Description": "moving, relocation", "Vendor": "u-haul, movers",
                        "Watch out": "U-Haul is also used to move equipment"},
    "Personal purchases": {"Description": "personal", "Vendor": "netflix, spotify, itunes",
                           "Watch out": "needs the business purpose to judge"},
    "Personal memberships and dues": {"Description": "membership, dues", "Vendor": "association, society",
                                      "Watch out": "also finds conference registrations"},
    "Salaries, wages, benefits": {"Description": "salary, wage, payroll", "Vendor": "employment, staffing",
                                  "Watch out": "temporary staffing agencies are paid wages indirectly"},
    "Service and incentive awards": {"Description": "award, plaque, incentive", "Vendor": "awards, trophy",
                                     "Watch out": "trophies for student competitions may be allowed"},
}


def show_results(df, label):
    if df.empty:
        st.info(f"No transactions found for this {label} search.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Transactions", f"{len(df):,}")
    c2.metric("Total amount", f"${df['Amount'].sum():,.2f}")
    c3.metric("Cardholders", f"{df['FullName'].nunique():,}")
    st.dataframe(df, hide_index=True)
    st.download_button(
        "Download results as CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"{label.lower()}_search_results.csv",
        mime="text/csv",
        key=f"download_{label}",
    )


tab_ask, tab_dashboard = st.tabs(["🔎 Ask the database", "🚩 Prohibited purchases dashboard"])

# ---------------------------------------------------------------------------
# Tab 1: natural-language questions
# ---------------------------------------------------------------------------

with tab_ask:
    st.write("Ask a question in plain English. Gemini writes the SQL query, which is then run on the P-card database.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", None)
        except Exception:  # no secrets file when running locally
            api_key = None
    if not api_key:
        api_key = st.text_input("Enter Google Gemini API Key:", type="password")

    user_query = st.text_input("Enter your audit question (e.g., 'Show top 10 highest transactions in 2014'):")

    if user_query and not api_key:
        st.warning("Please provide a Gemini API Key to ask questions.")
    elif user_query:
        client = genai.Client(api_key=api_key)
        prompt = f"""
You are a SQLite expert. Given the database schema below, write a single raw SQLite query to answer the user's request.
Return ONLY the raw SQL query. Do not wrap it in markdown block quotes (e.g. no ```sql), no explanation.
Dates in TransactionDate and PostedDate are text in the format M/D/YYYY H:MM:SS (no leading zeros).

Schema:
{get_db_schema()}

User Question: {user_query}
"""
        with st.spinner("Generating SQL query..."):
            try:
                response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
                sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()
                st.subheader("Generated SQL Query")
                st.code(sql_query, language="sql")

                if not sql_query.lstrip().upper().startswith(("SELECT", "WITH")):
                    st.error("Only SELECT queries are allowed.")
                else:
                    df = run_query(sql_query)
                    st.subheader("Query Results")
                    if not df.empty:
                        st.dataframe(df, hide_index=True)
                    else:
                        st.info("Query executed successfully, but returned no results.")
            except Exception as e:
                st.error(f"An error occurred: {e}")

# ---------------------------------------------------------------------------
# Tab 2: prohibited purchases dashboard
# ---------------------------------------------------------------------------

with tab_dashboard:
    st.header("Prohibited purchases dashboard")

    with st.expander("📖 How to use this dashboard", expanded=True):
        st.markdown(
            """
1. **Select the year** you want to audit (or *All years*).
2. Use the **Description search** to look for a keyword in what was bought
   (e.g. *beer*, *gift card*, *late fee*).
3. Use the **Vendor search** to look for a keyword in who was paid
   (e.g. *USPS*, *liquor*, *Shell*).
4. Not sure which keyword to use? Open **Suggested keywords** for ideas for each
   category that OSU prohibits on P-cards.
5. Review the results (largest amounts first) and download them as CSV for follow-up.

Searches are not case-sensitive and match any part of the text, so *post* also finds
*POST OFFICE*. A match is only a **potential** violation. Check the receipt and business
purpose before concluding that a control was breached.
"""
        )

    with st.expander("💡 Suggested keywords for each prohibited category"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Prohibited category": k,
                        "Try in Description search": v["Description"],
                        "Try in Vendor search": v["Vendor"],
                        "Watch out for": v["Watch out"],
                    }
                    for k, v in PROHIBITED_CATEGORIES.items()
                ]
            ),
            hide_index=True,
        )

    years = ["All years"] + get_years()
    year = st.selectbox("Year to search", years, index=1)

    col_desc, col_vendor = st.columns(2)

    with col_desc:
        st.subheader("🧾 Description search")
        st.caption("Searches the transaction **Description** field (what was purchased).")
        desc_kw = st.text_input("Keyword in description", placeholder="e.g. beer", key="desc_kw")

    with col_vendor:
        st.subheader("🏪 Vendor search")
        st.caption("Searches the **Vendor** field (who was paid).")
        vendor_kw = st.text_input("Keyword in vendor name", placeholder="e.g. USPS", key="vendor_kw")

    if desc_kw.strip():
        st.markdown(f"#### Description results for “{desc_kw.strip()}” ({year})")
        show_results(search_transactions("Description", desc_kw, year), "Description")

    if vendor_kw.strip():
        st.markdown(f"#### Vendor results for “{vendor_kw.strip()}” ({year})")
        show_results(search_transactions("Vendor", vendor_kw, year), "Vendor")

    if not desc_kw.strip() and not vendor_kw.strip():
        st.info("Enter a keyword in either search box to see matching transactions.")
