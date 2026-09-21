import os
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env
load_dotenv()

# Streamlit Page Setup
st.set_page_config(page_title="P-Card Forensic Audit Tool", layout="wide")
st.title("💳 P-Card Forensic Audit Assistant")
st.write("Ask natural language questions to query the local SQLite P-Card database.")

# Load API Key from .env or Streamlit Secrets or Sidebar Input
api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

if not api_key:
    api_key = st.sidebar.text_input("Enter Google Gemini API Key:", type="password")

if not api_key:
    st.warning("Please provide a Gemini API Key to proceed.")
    st.stop()

# Initialize Gemini Client
client = genai.Client(api_key=api_key)

# Function to extract schema from SQLite database
def get_db_schema(db_path="pcards.db"):
    if not os.path.exists(db_path):
        st.error(f"Database file `{db_path}` not found!")
        return ""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    return "\n".join([t[0] for t in tables if t[0]])

# Function to generate SQL query using Gemini
def generate_sql(user_query, schema_info):
    prompt = f"""
You are a SQLite expert. Given the database schema below, write a single raw SQLite query to answer the user's request.
Return ONLY the raw SQL query. Do not wrap it in markdown block quotes (e.g. no ```sql), no explanation.

Schema:
{schema_info}

User Question: {user_query}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    
    # Clean up any residual markdown formatting
    sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()
    return sql_query

# Get schema automatically
schema = get_db_schema()

# User input query
user_query = st.text_input("Enter your audit question (e.g., 'Show top 10 highest transactions'):")

if user_query and schema:
    with st.spinner("Generating SQL query..."):
        try:
            sql_query = generate_sql(user_query, schema)
            st.subheader("Generated SQL Query")
            st.code(sql_query, language="sql")

            # Execute query on SQLite database
            conn = sqlite3.connect("pcards.db")
            df = pd.read_sql_query(sql_query, conn)
            conn.close()

            st.subheader("Query Results")
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Query executed successfully, but returned no results.")

        except Exception as e:
            st.error(f"An error occurred: {e}")